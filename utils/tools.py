import logging

def convert_to_m3u(results, path):
    try:
        logging.debug(f"Starting to convert results to M3U and TXT at {path}")
        # 假设 results 是包含直播源 URL 的列表
        # 生成 TXT 文件，每行一个直播源 URL
        with open(path, 'w') as txt_file:
            for result in results:
                # 这里假设 result 包含 'url' 键
                if 'url' in result:
                    txt_file.write(result['url'] + '\n')

        # 生成 M3U 文件
        m3u_path = path.replace('.txt', '.m3u')
        with open(m3u_path, 'w') as m3u_file:
            m3u_file.write('#EXTM3U\n')
            for result in results:
                if 'url' in result:
                    # 这里简单设置频道名称，可根据实际情况修改
                    channel_name = result.get('name', 'Unknown Channel')
                    m3u_file.write(f'#EXTINF:-1, {channel_name}\n')
                    m3u_file.write(result['url'] + '\n')

        logging.debug(f"Successfully converted results to M3U and TXT at {path}")
    except Exception as e:
        logging.error(f"Error in convert_to_m3u: {e}", exc_info=True)
    
