#!/usr/bin/env python3
import asyncio
import logging
import os.path
import tempfile

from home.config import config
from home.camera.esp32 import WebClient
from home.util import parse_addr, send_datagram, stringify
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Optional

logger = logging.getLogger(__name__)
cam: Optional[WebClient] = None


async def pyssim(fn1: str, fn2: str) -> float:
    args = [config['pyssim']['bin']]
    if 'width' in config['pyssim']:
        args.extend(['--width', str(config['pyssim']['width'])])
    if 'height' in config['pyssim']:
        args.extend(['--height', str(config['pyssim']['height'])])
    args.extend([fn1, fn2])
    proc = await asyncio.create_subprocess_exec(*args,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error(f'pyssim({fn1}, {fn2}): pyssim returned {proc.returncode}, stderr: {stderr.decode().strip()}')

    return float(stdout.decode().strip())


class ESP32CamCaptureDiffNode:
    def __init__(self):
        self.client = WebClient(parse_addr(config['esp32cam_web_addr']))
        self.directory = tempfile.gettempdir()
        self.nextpic = 1
        self.first = True
        self.server_addr = parse_addr(config['node']['server_addr'])

        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.capture, 'interval', seconds=config['node']['interval'])
        self.scheduler.start()

    async def capture(self):
        logger.debug('capture: start')

        filename = self.getfilename()
        if not await self.client.capture(os.path.join(self.directory, filename)):
            logger.error('failed to capture')
            return

        self.nextpic = 1 if self.nextpic == 2 else 2
        if not self.first:
            score = await pyssim(filename, os.path.join(self.directory, self.getfilename()))
            logger.debug(f'pyssim: diff={score}')
            if score < config['pyssim']['threshold']:
                logger.info(f'score = {score}, informing central server')
                send_datagram(stringify([config['node']['name'], 2]), self.server_addr)

        self.first = False

        logger.debug('capture: done')

    def getfilename(self):
        return os.path.join(self.directory, f'{self.nextpic}.jpg')


if __name__ == '__main__':
    config.load('esp32cam_capture_diff_node')

    loop = asyncio.get_event_loop()
    ESP32CamCaptureDiffNode()
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
