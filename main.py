import asyncio
import aiohttp
import logging
import os
from collections import OrderedDict

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


# 异步获取 URL 内容
async def fetch_url(session, url):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.text()
            else:
                logging.warning(f"请求 {url} 失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求 {url} 时发生错误: {e}")
    return None


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
                name = info[1]
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    channels.append((name, url))
        i += 1
    return channels


# 解析 TXT 格式内容
def parse_txt_content(content):
    channels = []
    genre = None
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if line.endswith('#genre#'):
            genre = line.replace('#genre#', '').strip()
        elif line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name, url = parts
                if genre:
                    name = f"{genre}-{name}"
                channels.append((name, url))
    return channels


# 合并并去重频道
def merge_and_deduplicate(channels_list):
    all_channels = []
    for channels in channels_list:
        all_channels.extend(channels)
    unique_channels = list(OrderedDict(all_channels).items())
    return unique_channels


# 生成 M3U 文件
def generate_m3u_file(channels, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for name, url in channels:
            f.write(f'#EXTINF:-1,{name}\n')
            f.write(f'{url}\n')


# 生成 TXT 文件
def generate_txt_file(channels, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for name, url in channels:
            parts = name.split('-', 1)
            if len(parts) == 2:
                genre, name = parts
                f.write(f'{genre},#genre#\n')
                f.write(f'{name},{url}\n')
            else:
                f.write(f'{name},{url}\n')


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
        contents = await asyncio.gather(*tasks)

    all_channels = []
    for content in contents:
        if content:
            if '#EXTM3U' in content:
                channels = parse_m3u_content(content)
            else:
                channels = parse_txt_content(content)
            all_channels.append(channels)

    # 合并并去重频道
    unique_channels = merge_and_deduplicate(all_channels)

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u)
    generate_txt_file(unique_channels, output_txt)

    logging.info("成功生成 M3U 和 TXT 文件。")


if __name__ == '__main__':
    asyncio.run(main())
    
