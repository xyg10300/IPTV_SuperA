import asyncio
import aiohttp
import logging
import os
from collections import defaultdict
import re
import concurrent.futures

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 全局 EPG 接口配置
EPG_URL = "http://example.com/epg.xml"
# 回看天数范围
REPLAY_DAYS_RANGE = (3, 7)
# 最大响应时间（秒）
MAX_RESPONSE_TIME = 5

def read_subscription_file(file_path):
    """
    从文件中读取订阅的直播源 URL
    :param file_path: 订阅文件路径
    :return: 直播源 URL 列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        logging.error(f"订阅文件 {file_path} 未找到。")
        return []

async def fetch_content(session, url):
    """
    异步获取直播源内容
    :param session: aiohttp 会话
    :param url: 直播源 URL
    :return: 直播源内容
    """
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                return await response.text()
            else:
                logging.warning(f"请求 {url} 失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求 {url} 时出错: {e}")
    return None

def parse_m3u_content(content):
    """
    解析 M3U 格式的直播源内容
    :param content: 直播源内容
    :return: 频道信息列表
    """
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = line.split(',', 1)
            if len(info) == 2:
                metadata = info[0]
                name = info[1]
                tvg_id = re.search(r'tvg-id="([^"]+)"', metadata)
                tvg_name = re.search(r'tvg-name="([^"]+)"', metadata)
                tvg_logo = re.search(r'tvg-logo="([^"]+)"', metadata)
                group_title = re.search(r'group-title="([^"]+)"', metadata)
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    channel = {
                        'name': name,
                        'url': url,
                        'tvg_id': tvg_id.group(1) if tvg_id else None,
                        'tvg_name': tvg_name.group(1) if tvg_name else None,
                        'tvg_logo': tvg_logo.group(1) if tvg_logo else None,
                        'group_title': group_title.group(1) if group_title else '未分组',
                        'response_time': float('inf')
                    }
                    channels.append(channel)
        i += 1
    return channels

def parse_txt_content(content):
    """
    解析 TXT 格式的直播源内容
    :param content: 直播源内容
    :return: 频道信息列表
    """
    channels = []
    current_group = '未分组'
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if line.endswith('#genre#'):
            current_group = line.replace('#genre#', '').strip()
        elif line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name, url = parts
                channel = {
                    'name': name,
                    'url': url,
                    'tvg_id': None,
                    'tvg_name': None,
                    'tvg_logo': None,
                    'group_title': current_group,
                    'response_time': float('inf')
                }
                channels.append(channel)
    return channels

def merge_channels(channels_list):
    """
    合并多个频道列表并去重
    :param channels_list: 频道列表集合
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

async def test_channel_response(session, channel):
    """
    测试频道的响应时间
    :param session: aiohttp 会话
    :param channel: 频道信息
    :return: 更新响应时间后的频道信息
    """
    try:
        start_time = asyncio.get_running_loop().time()
        async with session.get(channel['url'], timeout=10) as response:
            if response.status == 200:
                end_time = asyncio.get_running_loop().time()
                channel['response_time'] = end_time - start_time
    except Exception as e:
        logging.error(f"测试 {channel['url']} 响应时间时出错: {e}")
    return channel

def group_channels_by_group_title(channels):
    """
    按分组标题对频道进行分组
    :param channels: 频道列表
    :return: 分组后的频道字典
    """
    grouped = defaultdict(list)
    for channel in channels:
        grouped[channel['group_title']].append(channel)
    return grouped

def generate_m3u_file(channels, output_path):
    """
    生成 M3U 文件
    :param channels: 频道列表
    :param output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write('#EXTM3U\n')
        for group_title in sorted(group_channels_by_group_title(channels)):
            group_channels = sorted(group_channels_by_group_title(channels)[group_title], key=lambda x: x['name'])
            for channel in group_channels:
                if channel['response_time'] < MAX_RESPONSE_TIME:
                    metadata = '#EXTINF:-1'
                    if channel['tvg_id']:
                        metadata += f' tvg-id="{channel["tvg_id"]}"'
                    if channel['tvg_name']:
                        metadata += f' tvg-name="{channel["tvg_name"]}"'
                    if channel['tvg_logo']:
                        metadata += f' tvg-logo="{channel["tvg_logo"]}"'
                    metadata += f' group-title="{channel["group_title"]}"'
                    metadata += f' catchup-days="{REPLAY_DAYS_RANGE[1]}" catchup-source="{EPG_URL}"'
                    for replay_days in range(*REPLAY_DAYS_RANGE):
                        replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
                        file.write(f'{metadata},{channel["name"]} (回看{replay_days}天)\n')
                        file.write(f'{replay_url}\n')

def generate_txt_file(channels, output_path):
    """
    生成 TXT 文件
    :param channels: 频道列表
    :param output_path: 输出文件路径
    """
    with open(output_path, 'w', encoding='utf-8') as file:
        for group_title in sorted(group_channels_by_group_title(channels)):
            group_channels = sorted(group_channels_by_group_title(channels)[group_title], key=lambda x: x['name'])
            file.write(f'{group_title},#genre#\n')
            for channel in group_channels:
                if channel['response_time'] < MAX_RESPONSE_TIME:
                    file.write(f'{channel["name"]},{channel["url"]}\n')
            file.write('\n')

async def main():
    subscription_file = 'config/subscribe.txt'
    output_m3u = 'output/result.m3u'
    output_txt = 'output/result.txt'

    # 确保输出目录存在
    output_dir = os.path.dirname(output_m3u)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 读取订阅文件
    urls = read_subscription_file(subscription_file)
    if not urls:
        logging.error("订阅文件中没有有效的 URL。")
        return

    # 异步获取所有直播源内容
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_content(session, url) for url in urls]
        contents = await asyncio.gather(*tasks)

    # 解析直播源内容
    all_channels = []
    def parse(content):
        if content:
            if '#EXTM3U' in content:
                return parse_m3u_content(content)
            else:
                return parse_txt_content(content)
        return []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        all_channels = list(executor.map(parse, contents))

    # 合并并去重频道
    unique_channels = merge_channels(all_channels)

    # 测试每个频道的响应时间
    async with aiohttp.ClientSession() as session:
        tasks = [test_channel_response(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u)
    generate_txt_file(unique_channels, output_txt)

    logging.info("成功生成 M3U 和 TXT 文件。")

if __name__ == "__main__":
    asyncio.run(main())
    
