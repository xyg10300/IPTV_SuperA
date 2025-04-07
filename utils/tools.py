import logging

def convert_to_m3u(results, path):
    try:
        logging.debug(f"Starting to convert results to M3U and TXT at {path}")
        # 假设这里是生成 M3U 和 TXT 文件的逻辑
        # 简单示例：将结果写入 TXT 文件
        with open(path, 'w') as txt_file:
            for result in results:
                txt_file.write(str(result) + '\n')
        # 生成 M3U 文件
        m3u_path = path.replace('.txt', '.m3u')
        with open(m3u_path, 'w') as m3u_file:
            m3u_file.write('#EXTM3U\n')
            for result in results:
                # 这里需要根据实际情况格式化 M3U 内容
                m3u_file.write(f'#EXTINF:-1, {result}\n')
                m3u_file.write('http://example.com/stream\n')  # 示例流地址
        logging.debug(f"Successfully converted results to M3U and TXT at {path}")
    except Exception as e:
        logging.error(f"Error in convert_to_m3u: {e}", exc_info=True)
    
