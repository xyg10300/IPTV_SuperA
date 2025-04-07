import asyncio
import aiohttp
import logging
from utils.speed import get_speed_with_download
from utils.tools import convert_to_m3u
from utils.config import config_instance

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_urls():
    urls = []
    try:
        with open('config/subscribe.txt', 'r') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.append(url)
        logging.info(f"Fetched {len(urls)} URLs from subscribe.txt")
    except FileNotFoundError:
        logging.error("config/subscribe.txt file not found.")
        return []
    tasks = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            task = asyncio.create_task(get_speed_with_download(url, session=session))
            tasks.append(task)
        try:
            results = await asyncio.gather(*tasks)
            logging.info(f"Successfully fetched results for {len(results)} URLs")
            return results
        except Exception as e:
            logging.error(f"Error occurred while fetching URLs: {e}")
            return []

def main():
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(fetch_urls())
    if not results:
        logging.error("No results obtained from fetching URLs.")
        return
    # 合并去重频道等操作
    # ...
    # 生成M3U文件
    try:
        logging.info("Starting to generate M3U and TXT files...")
        convert_to_m3u(path='output/result.txt')
        logging.info("M3U and TXT files generated successfully.")
    except Exception as e:
        logging.error(f"Error occurred while generating M3U and TXT files: {e}")

if __name__ == '__main__':
    main()
    
