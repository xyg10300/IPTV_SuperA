import asyncio
import aiohttp
import logging
import os
import re
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取订阅文件中的 URL
def read_subscribe_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到订阅文件: {file_path}")
        return []

# 异步获取 URL 内容并测试响应时间，多次请求取平均值
async def fetch_url(session, url, num_tries=3):
    total_time = 0
    successful_tries = 0
    for _ in range(num_tries):
        start_time = time.time()
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    await response.text()
                    elapsed_time = time.time() - start_time
                    total_time += elapsed_time
                    successful_tries += 1
                else:
                    logging.warning(f"请求 {url} 失败，状态码: {response.status}")
        except Exception as e:
            logging.error(f"请求 {url} 时发生错误: {e}")
    if successful_tries > 0:
        return total_time / successful_tries
    return float('inf')

# 解析 M3U 格式内容
def parse_m3u_content(content):
    channels = []
    lines = content.splitlines()
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = line.split(',', 1)
            if len(info) == 2:
                metadata = info[0]
                name = info[1]
                tvg_id = re.search(r'tvg-id="([^"]+)"', metadata)
                tvg_name = re.search(r'tvg-name="([^"]+)"', metadata)
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
    channels = []
    current_group = None
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
                    'group_title': current_group,
                    'response_time': float('inf')
                }
                channels.append(channel)
    return channels

# 合并并去重频道
def merge_and_deduplicate(channels_list):
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
    response_time = await fetch_url(session, channel['url'], num_tries)
    channel['response_time'] = response_time
    return channel

# 从文件读取要保留的组名和频道名
def read_include_list(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到包含列表文件: {file_path}")
        return []

# 生成 M3U 文件，增加 EPG 回放支持，可过滤响应时间过长的频道和特定组名或频道
def generate_m3u_file(channels, output_path, replay_days=7, max_response_time=float('inf'), 
                      include_groups=None, include_channels=None):
    group_channels = {}
    for channel in channels:
        # 过滤响应时间过长的频道
        if channel['response_time'] <= max_response_time:
            # 过滤特定组名或频道
            if ((include_groups is None or channel['group_title'] in include_groups) and
                (include_channels is None or channel['name'] in include_channels)):
                group_title = channel['group_title'] or ''
                group_channels.setdefault(group_title, []).append(channel)

    sorted_groups = sorted(group_channels.keys())

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for group_title in sorted_groups:
            group = group_channels[group_title]
            sorted_group = sorted(group, key=lambda x: x['response_time'])
            if group_title:
                f.write(f'#EXTGRP:{group_title}\n')
            for channel in sorted_group:
                metadata = '#EXTINF:-1'
                if channel['tvg_id']:
                    metadata += f' tvg-id="{channel["tvg_id"]}"'
                if channel['tvg_name']:
                    metadata += f' tvg-name="{channel["tvg_name"]}"'
                if channel['group_title']:
                    metadata += f' group-title="{channel["group_title"].rstrip(",")}"'
                replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
                f.write(f'{metadata},{channel["name"]}\n')
                f.write(f'{replay_url}\n')
            f.write('\n')

# 生成 TXT 文件，可过滤响应时间过长的频道和特定组名或频道
def generate_txt_file(channels, output_path, max_response_time=float('inf'), 
                      include_groups=None, include_channels=None):
    group_channels = {}
    for channel in channels:
        # 过滤响应时间过长的频道
        if channel['response_time'] <= max_response_time:
            # 过滤特定组名或频道
            if ((include_groups is None or channel['group_title'] in include_groups) and
                (include_channels is None or channel['name'] in include_channels)):
                group_title = channel['group_title'] or ''
                group_channels.setdefault(group_title, []).append(channel)

    sorted_groups = sorted(group_channels.keys())

    with open(output_path, 'w', encoding='utf-8') as f:
        for group_title in sorted_groups:
            group = group_channels[group_title]
            sorted_group = sorted(group, key=lambda x: x['response_time'])
            if group_title:
                f.write(f'{group_title}#genre#\n')
            for channel in sorted_group:
                f.write(f'{channel["name"]},{channel["url"]}\n')
            f.write('\n')

async def main():
    subscribe_file = 'config/subscribe.txt'
    output_m3u = 'output/result.m3u'
    output_txt = 'output/result.txt'
    include_list_file = 'config/include_list.txt'

    # 确保输出目录存在
    output_dir = os.path.dirname(output_m3u)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 读取订阅文件
    urls = read_subscribe_file(subscribe_file)
    if not urls:
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
        logging.error("未获取到有效的频道信息。")
        return

    # 测试每个频道的响应时间
    async with aiohttp.ClientSession() as session:
        tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 可配置最大响应时间，过滤掉响应时间过长的频道
    max_response_time = 5  # 单位：秒

    # 从文件读取要保留的组名和频道名
    include_list = read_include_list(include_list_file)
    include_groups = [item for item in include_list if item.startswith('group:')]
    include_groups = [group.replace('group:', '') for group in include_groups]
    include_channels = [item for item in include_list if not item.startswith('group:')]

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u, max_response_time=max_response_time, 
                      include_groups=include_groups, include_channels=include_channels)
    generate_txt_file(unique_channels, output_txt, max_response_time=max_response_time, 
                      include_groups=include_groups, include_channels=include_channels)

    logging.info("成功生成 M3U 和 TXT 文件。")

if __name__ == '__main__':
    asyncio.run(main())    
