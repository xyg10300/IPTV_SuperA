import asyncio
import aiohttp
import logging
import os
from collections import OrderedDict
import re
import time
import concurrent.futures

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 最大响应时间阈值（秒）
MAX_RESPONSE_TIME = 5.0

# 读取订阅文件中的 URL
def read_subscribe_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到订阅文件: {file_path}")
        return []

# 异步获取 URL 内容并测试响应时间
async def fetch_url(session, url):
    start_time = time.time()
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                elapsed_time = time.time() - start_time
                return content, elapsed_time
            else:
                logging.warning(f"请求 {url} 失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求 {url} 时发生错误: {e}")
    return None, float('inf')

# 解析 M3U 格式内容
def parse_m3u_content(content):
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
                        'group_title': group_title.group(1) if group_title else None,
                        'response_time': float('inf')
                    }
                    channels.append(channel)
        i += 1
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
                    'tvg_logo': None,
                    'group_title': current_group,
                    'response_time': float('inf')
                }
                channels.append(channel)
    return channels

# 合并并去重频道
def merge_and_deduplicate(channels_list):
    all_channels = []
    for channels in channels_list:
        all_channels.extend(channels)
    unique_channels = []
    url_set = set()
    for channel in all_channels:
        if channel['url'] not in url_set:
            unique_channels.append(channel)
            url_set.add(channel['url'])
    return unique_channels

# 测试每个频道的响应时间
async def test_channel_response_time(session, channel):
    start_time = time.time()
    try:
        async with session.get(channel['url'], timeout=10) as response:
            if response.status == 200:
                channel['response_time'] = time.time() - start_time
    except Exception as e:
        logging.error(f"测试 {channel['url']} 响应时间时发生错误: {e}")
    return channel

# 按频道名称归类频道
def group_channels_by_name(channels):
    grouped_channels = OrderedDict()
    for channel in channels:
        name = channel['name']
        if name not in grouped_channels:
            grouped_channels[name] = []
        grouped_channels[name].append(channel)
    return grouped_channels

# 生成 M3U 文件，增加 EPG 和台标支持，支持 72 小时至 7 天回看
def generate_m3u_file(channels, output_path, replay_days_range=(3, 7)):
    grouped_channels = group_channels_by_name(channels)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for name, channel_list in grouped_channels.items():
            sorted_channel_list = sorted(channel_list, key=lambda x: x['response_time'])
            first_channel = sorted_channel_list[0]
            metadata = '#EXTINF:-1'
            if first_channel['tvg_id']:
                metadata += f' tvg-id="{first_channel["tvg_id"]}"'
            if first_channel['tvg_name']:
                metadata += f' tvg-name="{first_channel["tvg_name"]}"'
            if first_channel['tvg_logo']:
                metadata += f' tvg-logo="{first_channel["tvg_logo"]}"'
            if first_channel['group_title']:
                metadata += f' group-title="{first_channel["group_title"]}"'
            for replay_days in range(replay_days_range[0], replay_days_range[1] + 1):
                for channel in sorted_channel_list:
                    replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
                    f.write(f'{metadata},{channel["name"]} (回看{replay_days}天，源{channel_list.index(channel) + 1})\n')
                    f.write(f'{replay_url}\n')

# 生成 TXT 文件
def generate_txt_file(channels, output_path):
    grouped_channels = group_channels_by_name(channels)
    with open(output_path, 'w', encoding='utf-8') as f:
        for name, channel_list in grouped_channels.items():
            sorted_channel_list = sorted(channel_list, key=lambda x: x['response_time'])
            for channel in sorted_channel_list:
                f.write(f'{channel["name"]},{channel["url"]}\n')

async def main():
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
        logging.error("订阅文件中没有有效的 URL。")
        return

    # 异步获取所有 URL 的内容
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    all_channels = []

    def parse_content(result):
        content, _ = result
        if content:
            if '#EXTM3U' in content:
                return parse_m3u_content(content)
            else:
                return parse_txt_content(content)
        return []

    with concurrent.futures.ThreadPoolExecutor() as executor:
        all_channels = list(executor.map(parse_content, results))

    # 合并并去重频道
    unique_channels = merge_and_deduplicate(all_channels)

    # 测试每个频道的响应时间
    async with aiohttp.ClientSession() as session:
        tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 过滤掉响应时间过长的频道
    valid_channels = [channel for channel in unique_channels if channel['response_time'] < MAX_RESPONSE_TIME]

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(valid_channels, output_m3u)
    generate_txt_file(valid_channels, output_txt)

    logging.info("成功生成 M3U 和 TXT 文件。")

if __name__ == '__main__':
    asyncio.run(main())
    
