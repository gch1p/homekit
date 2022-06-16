#!/usr/bin/env python3
import asyncio
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..')
    )
])

import src.home.telegram.aio as telegram

from src.home.config import config


async def main():
    await telegram.send_message(f'test message')
    await telegram.send_photo('/tmp/3.jpg')
    await telegram.send_photo('/tmp/4.jpg')


if __name__ == '__main__':
    config.load('test_telegram_aio_send_photo')

    loop = asyncio.get_event_loop()
    asyncio.ensure_future(main())

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
