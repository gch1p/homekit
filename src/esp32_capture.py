#!/usr/bin/env python3
import asyncio
import logging
import os.path

from argparse import ArgumentParser
from home.camera.esp32 import WebClient
from home.util import parse_addr, Addr
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)
cam: Optional[WebClient] = None


class ESP32Capture:
    def __init__(self, addr: Addr, interval: float, output_directory: str):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client = WebClient(addr)
        self.output_directory = output_directory
        self.interval = interval

        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.capture, 'interval', seconds=arg.interval)
        self.scheduler.start()

    async def capture(self):
        self.logger.debug('capture: start')
        now = datetime.now()
        filename = os.path.join(
            self.output_directory,
            now.strftime('%Y-%m-%d-%H:%M:%S.%f.jpg')
        )
        if not await self.client.capture(filename):
            self.logger.error('failed to capture')
        self.logger.debug('capture: done')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--addr', type=str, required=True)
    parser.add_argument('--output-directory', type=str, required=True)
    parser.add_argument('--interval', type=float, default=0.5)
    parser.add_argument('--verbose', action='store_true')
    arg = parser.parse_args()

    if arg.verbose:
        logging.basicConfig(level=logging.DEBUG)

    loop = asyncio.get_event_loop()

    ESP32Capture(parse_addr(arg.addr), arg.interval, arg.output_directory)
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
