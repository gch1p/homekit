#!/usr/bin/env python3
import smbus
import argparse
import asyncio
import json
import logging

from home.config import config
from home.util import parse_addr

logger = logging.getLogger(__name__)
bus = None
lock = asyncio.Lock()
delay = 0.01


async def si7021_read():
    async with lock:
        await asyncio.sleep(delay)

        # these are still blocking... meh
        raw = bus.read_i2c_block_data(0x40, 0xE3, 2)
        temp = 175.72 * (raw[0] << 8 | raw[1]) / 65536.0 - 46.85

        raw = bus.read_i2c_block_data(0x40, 0xE5, 2)
        rh = 125.0 * (raw[0] << 8 | raw[1]) / 65536.0 - 6.0

        return rh, temp


async def handle_client(reader, writer):
    request = None
    while request != 'quit':
        try:
            request = await reader.read(255)
            if request == b'\x04':
                break
            request = request.decode('utf-8').strip()
        except Exception:
            break

        if request == 'read':
            try:
                rh, temp = await asyncio.wait_for(si7021_read(), timeout=3)
                data = dict(humidity=rh, temp=temp)
            except asyncio.TimeoutError as e:
                logger.exception(e)
                data = dict(error='i2c call timed out')
        else:
            data = dict(error='invalid request')

        writer.write((json.dumps(data) + '\r\n').encode('utf-8'))
        try:
            await writer.drain()
        except ConnectionResetError:
            pass

    writer.close()


async def run_server(host, port):
    server = await asyncio.start_server(handle_client, host, port)
    async with server:
        logger.info('Server started.')
        await server.serve_forever()


if __name__ == '__main__':
    config.load()

    host, port = parse_addr(config['server']['listen'])

    delay = float(config['smbus']['delay'])
    bus = smbus.SMBus(int(config['smbus']['bus']))

    try:
        asyncio.run(run_server(host, port))
    except KeyboardInterrupt:
        logging.info('Exiting...')
