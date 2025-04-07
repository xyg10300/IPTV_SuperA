import asyncio
import aiohttp
import logging
import os
import re
from collections import OrderedDict

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 读取订阅文件
def read_subscribe_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"订阅文件 {file_path} 未找到。")
        return []

# 异步抓取直播源信息
async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            else:
                logging.warning(f"请求 {url} 失败，状态码: {response.status}")
                return None
    except Exception as e:
        logging.error(f"请求 {url} 时发生错误: {e}")
        return None

# 解析 M3U 内容，提取频道信息
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
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    # 提取 EPG 和台标信息
                    epg = re.search(r'tvg-id="([^"]+)"', metadata)
                    logo = re.search(r'tvg-logo="([^"]+)"', metadata)
                    channel = {
                        'name': name,
                        'url': url,
                        'epg': epg.group(1) if epg else None,
                        'logo': logo.group(1) if logo else None
                    }
                    channels.append(channel)
        i += 1
    return channels

# 合并和去重频道
def merge_and_deduplicate_channels(channels_list):
    all_channels = []
    for channels in channels_list:
        all_channels.extend(channels)
    unique_channels = list(OrderedDict((channel['url'], channel) for channel in all_channels).values())
    return unique_channels

# 生成 M3U 文件
def generate_m3u_file(channels, output_path, replay_days=3):
    with open(output_path, 'w') as f:
        f.write('#EXTM3U\n')
        for channel in channels:
            metadata = f'#EXTINF:-1'
            if channel['epg']:
                metadata += f' tvg-id="{channel["epg"]}"'
            if channel['logo']:
                metadata += f' tvg-logo="{channel["logo"]}"'
            # 添加回放信息
            replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
            f.write(f'{metadata}, {channel["name"]}\n')
            f.write(f'{replay_url}\n')

# 生成 TXT 文件
def generate_txt_file(channels, output_path):
    with open(output_path, 'w') as f:
        for channel in channels:
            f.write(f'{channel["url"]}\n')

async def main():
    subscribe_file = 'subscribe.txt'
    output_m3u = 'output/result.m3u'
    output_txt = 'output/result.txt'

    # 确保输出目录存在
    output_dir = os.path.dirname(output_m3u)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 读取订阅文件
    urls = read_subscribe_file(subscribe_file)
    if not urls:
        logging.error("未找到有效的订阅 URL。")
        return

    # 异步抓取直播源信息
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        contents = await asyncio.gather(*tasks)

    # 解析和合并频道
    channels_list = []
    for content in contents:
        if content:
            channels = parse_m3u_content(content)
            channels_list.append(channels)
    unique_channels = merge_and_deduplicate_channels(channels_list)

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u)
    generate_txt_file(unique_channels, output_txt)

    logging.info("M3U 和 TXT 文件生成成功。")

if __name__ == '__main__':
    asyncio.run(main())
    
