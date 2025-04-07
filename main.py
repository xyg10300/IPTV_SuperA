import asyncio
import aiohttp
import logging
import os
from collections import OrderedDict
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
                group_title = re.search(r'group-title="([^"]+)"', metadata)
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    channel = {
                        'name': name,
                        'url': url,
                        'tvg_id': tvg_id.group(1) if tvg_id else None,
                        'tvg_name': tvg_name.group(1) if tvg_name else None,
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


# 测试每个频道的响应时间，显示实时响应时间
async def test_channel_response_time(session, channel):
    start_time = time.time()
    try:
        async with session.get(channel['url'], timeout=10) as response:
            if response.status == 200:
                elapsed_time = time.time() - start_time
                channel['response_time'] = elapsed_time
                logging.info(f"频道 {channel['name']} 的响应时间: {elapsed_time:.2f} 秒")
    except Exception as e:
        logging.error(f"测试 {channel['url']} 响应时间时发生错误: {e}")
    return channel


# 生成 M3U 文件，增加 EPG 回放支持
def generate_m3u_file(channels, output_path, replay_days=7):
    sorted_channels = sorted(channels, key=lambda x: x['response_time'])
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for channel in sorted_channels:
            metadata = '#EXTINF:-1'
            if channel['tvg_id']:
                metadata += f' tvg-id="{channel["tvg_id"]}"'
            if channel['tvg_name']:
                metadata += f' tvg-name="{channel["tvg_name"]}"'
            if channel['group_title']:
                metadata += f' group-title="{channel["group_title"]}"'
            # 添加回放参数
            replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
            f.write(f'{metadata},{channel["name"]}\n')
            f.write(f'{replay_url}\n')


# 生成 TXT 文件
def generate_txt_file(channels, output_path):
    sorted_channels = sorted(channels, key=lambda x: x['response_time'])
    with open(output_path, 'w', encoding='utf-8') as f:
        current_group = None
        for channel in sorted_channels:
            group_title = channel['group_title']
            if group_title and group_title != current_group:
                if current_group is not None:
                    f.write('\n')
                f.write(f'{group_title},#genre#\n')
                current_group = group_title
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
    for content, _ in results:
        if content:
            if '#EXTM3U' in content:
                channels = parse_m3u_content(content)
            else:
                channels = parse_txt_content(content)
            all_channels.append(channels)

    # 合并并去重频道
    unique_channels = merge_and_deduplicate(all_channels)

    # 测试每个频道的响应时间
    async with aiohttp.ClientSession() as session:
        tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u)
    generate_txt_file(unique_channels, output_txt)

    logging.info("成功生成 M3U 和 TXT 文件。")


if __name__ == '__main__':
    asyncio.run(main())
