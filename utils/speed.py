import asyncio
import http.cookies
import json
import re
import subprocess
from time import time
from urllib.parse import quote, urlparse

import m3u8
from aiohttp import ClientSession, TCPConnector
from utils.config import config_instance

http.cookies._is_legal_key = lambda _: True
cache = {}

async def get_speed_with_download(url: str, session: ClientSession = None, timeout: int = config_instance.sort_timeout) -> dict[str, float | None]:
    start_time = time()
    total_size = 0
    total_time = 0
    info = {'speed': None, 'delay': None}
    if session is None:
        session = ClientSession(connector=TCPConnector(ssl=False), trust_env=True)
        created_session = True
    else:
        created_session = False
    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                raise Exception("Invalid response")
            info['delay'] = int(round((time() - start_time) * 1000))
            async for chunk in response.content.iter_any():
                if chunk:
                    total_size += len(chunk)
    except:
        pass
    finally:
        if total_size > 0:
            total_time += time() - start_time
            info['speed'] = ((total_size / total_time) if total_time > 0 else 0) / 1024 / 1024
        if created_session:
            await session.close()
        return info
    
