import asyncio
import aiohttp
from utils.speed import get_speed
from utils.tools import convert_to_m3u
from utils.config import config_instance

async def fetch_urls():
    urls = []
    with open('config/subscribe.txt', 'r') as f:
        for line in f:
            url = line.strip()
            if url:
                urls.append(url)
    tasks = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            task = asyncio.create_task(get_speed(url, session=session))
            tasks.append(task)
        results = await asyncio.gather(*tasks)
    return results

def main():
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(fetch_urls())
    # 合并去重频道等操作
    # ...
    # 生成M3U文件
    convert_to_m3u(path='output/result.txt')

if __name__ == '__main__':
    main()