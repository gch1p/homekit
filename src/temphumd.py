#!/usr/bin/env python3
import asyncio
import json
import logging

from typing import Optional

from home.config import config
from home.temphum import SensorType, create_sensor, TempHumSensor

logger = logging.getLogger(__name__)
sensor: Optional[TempHumSensor] = None
lock = asyncio.Lock()
delay = 0.01


async def get_measurements():
    async with lock:
        await asyncio.sleep(delay)

        temp = sensor.temperature()
        rh = sensor.humidity()

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
                rh, temp = await asyncio.wait_for(get_measurements(), timeout=3)
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

    if 'measure_delay' in config['sensor']:
        delay = float(config['sensor']['measure_delay'])

    sensor = create_sensor(SensorType(config['sensor']['type']),
                           int(config['sensor']['bus']))

    try:
        host, port = config.get_addr('server.listen')
        asyncio.run(run_server(host, port))
    except KeyboardInterrupt:
        logging.info('Exiting...')
