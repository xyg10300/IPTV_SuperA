import asyncio
import aiohttp
import logging
import os
import re
import time

# 配置日志，设置日志级别为 INFO，指定日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 读取订阅文件中的 URL
def read_subscribe_file(file_path):
    """
    从指定文件中读取订阅的 URL 列表。
    :param file_path: 订阅文件的路径
    :return: URL 列表，如果文件不存在则返回空列表
    """
    try:
        # 以只读模式打开文件，并指定编码为 UTF-8
        with open(file_path, 'r', encoding='utf-8') as f:
            # 读取文件中的每一行，去除首尾空格，过滤掉空行
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        # 若文件未找到，记录错误日志并返回空列表
        logging.error(f"未找到订阅文件: {file_path}")
        return []


# 异步获取 URL 内容并测试响应时间，多次请求取平均值
async def fetch_url(session, url, num_tries=3):
    """
    异步获取指定 URL 的内容，并测试其响应时间。多次请求取平均值以减少网络波动的影响。
    :param session: aiohttp 客户端会话对象
    :param url: 要请求的 URL
    :param num_tries: 尝试请求的次数，默认为 3 次
    :return: 平均响应时间，如果请求失败则返回无穷大
    """
    total_time = 0
    successful_tries = 0
    for _ in range(num_tries):
        start_time = time.time()
        try:
            # 发起异步 GET 请求，设置超时时间为 10 秒
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    # 读取响应内容
                    await response.text()
                    elapsed_time = time.time() - start_time
                    total_time += elapsed_time
                    successful_tries += 1
                else:
                    # 若请求状态码不为 200，记录警告日志
                    logging.warning(f"请求 {url} 失败，状态码: {response.status}")
        except Exception as e:
            # 若请求过程中发生异常，记录错误日志
            logging.error(f"请求 {url} 时发生错误: {e}")
    if successful_tries > 0:
        # 计算平均响应时间
        return total_time / successful_tries
    return float('inf')


# 解析 M3U 格式内容
def parse_m3u_content(content):
    """
    解析 M3U 格式的内容，提取频道信息。
    :param content: M3U 格式的文本内容
    :return: 频道信息列表
    """
    channels = []
    lines = content.splitlines()
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            # 分割元数据和频道名称
            info = line.split(',', 1)
            if len(info) == 2:
                metadata = info[0]
                name = info[1]
                # 提取 tvg-id
                tvg_id = re.search(r'tvg-id="([^"]+)"', metadata)
                # 提取 tvg-name
                tvg_name = re.search(r'tvg-name="([^"]+)"', metadata)
                # 提取 group-title
                group_title = re.search(r'group-title="([^"]+)"', metadata)
                if i + 1 < len(lines):
                    url = lines[i + 1].strip()
                    channel = {
                        'name': name,
                        'url': url,
                        'tvg_id': tvg_id.group(1) if tvg_id else None,
                        'tvg_name': tvg_name.group(1) if tvg_name else None,
                        'group_title': group_title.group(1) if group_title else None,
                        'response_time': float('inf')
                    }
                    channels.append(channel)
    return channels


# 解析 TXT 格式内容
def parse_txt_content(content):
    """
    解析 TXT 格式的内容，提取频道信息。
    :param content: TXT 格式的文本内容
    :return: 频道信息列表
    """
    channels = []
    current_group = None
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if line.endswith('#genre#'):
            # 更新当前频道组名称
            current_group = line.replace('#genre#', '').strip()
        elif line:
            # 分割频道名称和 URL
            parts = line.split(',', 1)
            if len(parts) == 2:
                name, url = parts
                channel = {
                    'name': name,
                    'url': url,
                    'tvg_id': None,
                    'tvg_name': None,
                    'group_title': current_group,
                    'response_time': float('inf')
                }
                channels.append(channel)
    return channels


# 合并并去重频道
def merge_and_deduplicate(channels_list):
    """
    合并多个频道列表，并去除重复的频道。
    :param channels_list: 频道列表的列表
    :return: 去重后的频道列表
    """
    unique_channels = []
    url_set = set()
    for channels in channels_list:
        for channel in channels:
            if channel['url'] not in url_set:
                unique_channels.append(channel)
                url_set.add(channel['url'])
    return unique_channels


# 测试每个频道的响应时间
async def test_channel_response_time(session, channel, num_tries=3):
    """
    测试单个频道的响应时间。
    :param session: aiohttp 客户端会话对象
    :param channel: 频道信息字典
    :param num_tries: 尝试请求的次数，默认为 3 次
    :return: 更新响应时间后的频道信息字典
    """
    response_time = await fetch_url(session, channel['url'], num_tries)
    channel['response_time'] = response_time
    return channel


# 分组并排序频道
def group_and_sort_channels(channels, max_response_time=float('inf')):
    """
    对频道进行分组，并按响应时间排序。
    :param channels: 频道信息列表
    :param max_response_time: 最大响应时间，超过该时间的频道将被过滤掉，默认为无穷大
    :return: 分组后的频道字典和排序后的组名列表
    """
    group_channels = {}
    for channel in channels:
        if channel['response_time'] <= max_response_time:
            group_title = channel['group_title'] or ''
            group_channels.setdefault(group_title, []).append(channel)

    sorted_groups = sorted(group_channels.keys())
    for group in group_channels.values():
        group.sort(key=lambda x: x['response_time'])

    return group_channels, sorted_groups


# 生成 M3U 文件，增加 EPG 回放支持
def generate_m3u_file(channels, output_path, replay_days=7, max_response_time=float('inf')):
    """
    生成 M3U 格式的文件，包含 EPG 回放功能。
    :param channels: 频道信息列表
    :param output_path: 输出文件的路径
    :param replay_days: 可回放的天数，默认为 7 天
    :param max_response_time: 最大响应时间，超过该时间的频道将被过滤掉，默认为无穷大
    """
    group_channels, sorted_groups = group_and_sort_channels(channels, max_response_time)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for group_title in sorted_groups:
            group = group_channels[group_title]
            if group_title:
                f.write(f'#EXTGRP:{group_title}\n')
            for channel in group:
                metadata = '#EXTINF:-1'
                if channel['tvg_id']:
                    metadata += f' tvg-id="{channel["tvg_id"]}"'
                if channel['tvg_name']:
                    metadata += f' tvg-name="{channel["tvg_name"]}"'
                if channel['group_title']:
                    metadata += f' group-title="{channel["group_title"].rstrip(",")}"'
                # 构建带有回放参数的 URL
                replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
                f.write(f'{metadata},{channel["name"]}\n')
                f.write(f'{replay_url}\n')
            f.write('\n')


# 生成 TXT 文件
def generate_txt_file(channels, output_path, max_response_time=float('inf')):
    """
    生成 TXT 格式的文件，记录频道信息。
    :param channels: 频道信息列表
    :param output_path: 输出文件的路径
    :param max_response_time: 最大响应时间，超过该时间的频道将被过滤掉，默认为无穷大
    """
    group_channels, sorted_groups = group_and_sort_channels(channels, max_response_time)

    with open(output_path, 'w', encoding='utf-8') as f:
        for group_title in sorted_groups:
            group = group_channels[group_title]
            if group_title:
                f.write(f'{group_title}#genre#\n')
            for channel in group:
                f.write(f'{channel["name"]},{channel["url"]}\n')
            f.write('\n')


async def main():
    """
    主函数，协调整个流程，包括读取订阅文件、获取 URL 内容、解析频道信息、测试响应时间、生成文件等。
    """
    subscribe_file = 'config/subscribe.txt'
    output_m3u = 'output/result.m3u'
    output_txt = 'output/result.txt'

    # 确保输出目录存在
    output_dir = os.path.dirname(output_m3u)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 读取订阅文件
    urls = read_subscribe_file(subscribe_file)
    if not urls:
        # 若订阅文件中没有有效的 URL，记录错误日志并退出
        logging.error("订阅文件中没有有效的 URL。")
        return

    # 异步获取所有 URL 的内容
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    all_channels = []
    for content, _ in zip(results, urls):
        if content is not None:
            if '#EXTM3U' in content:
                channels = parse_m3u_content(content)
            else:
                channels = parse_txt_content(content)
            all_channels.append(channels)

    # 合并并去重频道
    unique_channels = merge_and_deduplicate(all_channels)

    if not unique_channels:
        # 若未获取到有效的频道信息，记录错误日志并退出
        logging.error("未获取到有效的频道信息。")
        return

    # 测试每个频道的响应时间
    async with aiohttp.ClientSession() as session:
        tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 可配置最大响应时间，过滤掉响应时间过长的频道
    max_response_time = 5  # 单位：秒
    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u, max_response_time=max_response_time)
    generate_txt_file(unique_channels, output_txt, max_response_time=max_response_time)

    logging.info("成功生成 M3U 和 TXT 文件。")


if __name__ == '__main__':
    asyncio.run(main())
    
