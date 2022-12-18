import asyncio
import logging

from pyA20.gpio import gpio
from pyA20.gpio import port as gpioport
from ..util import Addr

logger = logging.getLogger(__name__)


class RelayServer:
    OFF = 1
    ON = 0

    def __init__(self,
                 pinname: str,
                 addr: Addr):
        if not hasattr(gpioport, pinname):
            raise ValueError(f'invalid pin {pinname}')

        self.pin = getattr(gpioport, pinname)
        self.addr = addr

        gpio.init()
        gpio.setcfg(self.pin, gpio.OUTPUT)

        self.lock = asyncio.Lock()

    def run(self):
        asyncio.run(self.run_server())

    async def relay_set(self, value):
        async with self.lock:
            gpio.output(self.pin, value)

    async def relay_get(self):
        async with self.lock:
            return int(gpio.input(self.pin)) == RelayServer.ON

    async def handle_client(self, reader, writer):
        request = None
        while request != 'quit':
            try:
                request = await reader.read(255)
                if request == b'\x04':
                    break
                request = request.decode('utf-8').strip()
            except Exception:
                break

            data = 'unknown'
            if request == 'on':
                await self.relay_set(RelayServer.ON)
                logger.debug('set on')
                data = 'ok'

            elif request == 'off':
                await self.relay_set(RelayServer.OFF)
                logger.debug('set off')
                data = 'ok'

            elif request == 'get':
                status = await self.relay_get()
                data = 'on' if status is True else 'off'

            writer.write((data + '\r\n').encode('utf-8'))
            try:
                await writer.drain()
            except ConnectionError:
                break

        try:
            writer.close()
        except ConnectionError:
            pass

    async def run_server(self):
        host, port = self.addr
        server = await asyncio.start_server(self.handle_client, host, port)
        async with server:
            logger.info('Server started.')
            await server.serve_forever()
