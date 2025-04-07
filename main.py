import asyncio
import aiohttp
import logging
import os
from collections import OrderedDict
import re
import time
import socket

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 定义不同网络的测试地址
NETWORK_TEST_ADDRESSES = {
    "中国移动": "211.136.25.153",
    "中国电信": "202.96.128.166",
    "中国联通": "202.101.172.35"
}

# 示例 VPN 代理地址，需要根据实际情况修改
VPN_PROXY = "http://127.0.0.1:7897"


# 读取订阅文件中的 URL
def read_subscribe_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到订阅文件: {file_path}")
        return []


# 异步获取 URL 内容并测试响应时间，区分 IPv4 和 IPv6，支持 VPN 代理
async def fetch_url(session, url):
    ipv4_start_time = time.time()
    ipv4_response = None
    ipv4_elapsed_time = float('inf')
    ipv6_start_time = time.time()
    ipv6_response = None
    ipv6_elapsed_time = float('inf')

    try:
        # 尝试 IPv4 请求
        async with session.get(url, timeout=10, family=socket.AF_INET) as response:
            if response.status == 200:
                ipv4_response = await response.text()
                ipv4_elapsed_time = time.time() - ipv4_start_time
    except Exception as e:
        logging.error(f"IPv4 请求 {url} 时发生错误: {e}")

    try:
        # 尝试 IPv6 请求
        async with session.get(url, timeout=10, family=socket.AF_INET6) as response:
            if response.status == 200:
                ipv6_response = await response.text()
                ipv6_elapsed_time = time.time() - ipv6_start_time
    except Exception as e:
        logging.error(f"IPv6 请求 {url} 时发生错误: {e}")

    # 选择响应时间更短的结果
    if ipv4_elapsed_time < ipv6_elapsed_time:
        return ipv4_response, ipv4_elapsed_time
    else:
        return ipv6_response, ipv6_elapsed_time


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
                        'response_time': {
                            "中国移动": float('inf'),
                            "中国电信": float('inf'),
                            "中国联通": float('inf')
                        }
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
                    'response_time': {
                        "中国移动": float('inf'),
                        "中国电信": float('inf'),
                        "中国联通": float('inf')
                    }
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


# 测试网络连通性，判断当前网络运营商
async def test_network(session):
    best_network = None
    best_time = float('inf')
    for network, address in NETWORK_TEST_ADDRESSES.items():
        try:
            start_time = time.time()
            async with session.get(f"http://{address}", timeout=5) as response:
                if response.status == 200:
                    elapsed_time = time.time() - start_time
                    if elapsed_time < best_time:
                        best_time = elapsed_time
                        best_network = network
        except Exception as e:
            logging.error(f"测试 {network} 网络连通性时发生错误: {e}")
    return best_network


# 测试每个频道在不同网络下的响应时间
async def test_channel_response_time(session, channel):
    for network, address in NETWORK_TEST_ADDRESSES.items():
        try:
            start_time = time.time()
            async with session.get(channel['url'], timeout=10) as response:
                if response.status == 200:
                    channel['response_time'][network] = time.time() - start_time
        except Exception as e:
            logging.error(f"在 {network} 网络下测试 {channel['url']} 响应时间时发生错误: {e}")
    return channel


# 生成 M3U 文件，增加 EPG 回放支持
def generate_m3u_file(channels, output_path, replay_days=7, current_network=None):
    if current_network:
        sorted_channels = sorted(channels, key=lambda x: x['response_time'][current_network])
    else:
        sorted_channels = channels
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
def generate_txt_file(channels, output_path, current_network=None):
    if current_network:
        sorted_channels = sorted(channels, key=lambda x: x['response_time'][current_network])
    else:
        sorted_channels = channels
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

    # 创建支持 VPN 代理的会话
    proxy = os.getenv('VPN_PROXY', VPN_PROXY)
    connector = aiohttp.TCPConnector(limit_per_host=10)
    async with aiohttp.ClientSession(connector=connector, proxy=proxy) as session:
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

    # 测试当前网络运营商
    proxy = os.getenv('VPN_PROXY', VPN_PROXY)
    connector = aiohttp.TCPConnector(limit_per_host=10)
    async with aiohttp.ClientSession(connector=connector, proxy=proxy) as session:
        current_network = await test_network(session)
    logging.info(f"当前网络运营商: {current_network}")

    # 测试每个频道在不同网络下的响应时间
    proxy = os.getenv('VPN_PROXY', VPN_PROXY)
    connector = aiohttp.TCPConnector(limit_per_host=10)
    async with aiohttp.ClientSession(connector=connector, proxy=proxy) as session:
        tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 生成 M3U 和 TXT 文件
    generate_m3u_file(unique_channels, output_m3u, current_network=current_network)
    generate_txt_file(unique_channels, output_txt, current_network=current_network)

    logging.info("成功生成 M3U 和 TXT 文件。")


if __name__ == '__main__':
    asyncio.run(main())
    
