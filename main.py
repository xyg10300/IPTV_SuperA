import asyncio
import aiohttp
import logging
import os
from utils.speed import get_speed_with_download
from utils.tools import convert_to_m3u
from utils.config import config_instance

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_urls():
    urls = []
    try:
        if not os.path.exists('config'):
            logging.error("Config directory not found.")
            return []
        if not os.path.exists('config/subscribe.txt'):
            logging.error("config/subscribe.txt file not found.")
            return []
        with open('config/subscribe.txt', 'r') as f:
            for line in f:
                url = line.strip()
                if url:
                    urls.append(url)
        logging.info(f"Fetched {len(urls)} URLs from subscribe.txt")
    except Exception as e:
        logging.error(f"Error reading subscribe.txt: {e}")
        return []
    tasks = []
    async with aiohttp.ClientSession() as session:
        for url in urls:
            task = asyncio.create_task(get_speed_with_download(url, session=session))
            tasks.append(task)
        try:
            results = await asyncio.gather(*tasks)
            valid_results = [res for res in results if res]
            logging.info(f"Successfully fetched results for {len(valid_results)} URLs")
            return valid_results
        except Exception as e:
            logging.error(f"Error occurred while fetching URLs: {e}")
            return []

def main():
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(fetch_urls())
    if not results:
        logging.error("No valid results obtained from fetching URLs.")
        return
    # 确保输出目录存在
    output_dir = 'output'
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logging.info(f"Created output directory: {output_dir}")
        except Exception as e:
            logging.error(f"Failed to create output directory: {e}")
            return
    # 生成M3U和TXT文件
    try:
        logging.info("Starting to generate M3U and TXT files...")
        convert_to_m3u(path=os.path.join(output_dir, 'result.txt'))
        m3u_file = os.path.join(output_dir, 'result.m3u')
        txt_file = os.path.join(output_dir, 'result.txt')
        if os.path.exists(m3u_file) and os.path.exists(txt_file):
            logging.info("M3U and TXT files generated successfully.")
        else:
            logging.error("Failed to generate M3U and/or TXT files.")
    except Exception as e:
        logging.error(f"Error occurred while generating M3U and TXT files: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
    
