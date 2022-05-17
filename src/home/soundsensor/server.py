import asyncio
import json
import logging
import threading

from ..config import config
from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPNotFound
)

from typing import Type
from ..util import Addr, stringify, format_tb

logger = logging.getLogger(__name__)


class SoundSensorHitHandler(asyncio.DatagramProtocol):
    def datagram_received(self, data, addr):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error('failed to parse json datagram')
            logger.exception(e)
            return

        try:
            name, hits = data
        except (ValueError, IndexError) as e:
            logger.error('failed to unpack data')
            logger.exception(e)
            return

        self.handler(name, hits)

    def handler(self, name: str, hits: int):
        pass


class SoundSensorServer:
    def __init__(self,
                 addr: Addr,
                 handler_impl: Type[SoundSensorHitHandler]):
        self.addr = addr
        self.impl = handler_impl

        self._recording_lock = threading.Lock()
        self._recording_enabled = True

        if self.guard_control_enabled():
            if 'guard_recording_default' in config['server']:
                self._recording_enabled = config['server']['guard_recording_default']

    def guard_control_enabled(self) -> bool:
        return 'guard_control' in config['server'] and config['server']['guard_control'] is True

    def set_recording(self, enabled: bool):
        with self._recording_lock:
            self._recording_enabled = enabled

    def is_recording_enabled(self) -> bool:
        with self._recording_lock:
            return self._recording_enabled

    def run(self):
        if self.guard_control_enabled():
            t = threading.Thread(target=self.run_guard_server)
            t.daemon = True
            t.start()

        loop = asyncio.get_event_loop()
        t = loop.create_datagram_endpoint(self.impl, local_addr=self.addr)
        loop.run_until_complete(t)
        loop.run_forever()

    def run_guard_server(self):
        routes = web.RouteTableDef()

        def ok(data=None):
            if data is None:
                data = 1
            response = {'response': data}
            return web.json_response(response, dumps=stringify)

        @web.middleware
        async def errors_handler_middleware(request, handler):
            try:
                response = await handler(request)
                return response
            except HTTPNotFound:
                return web.json_response({'error': 'not found'}, status=404)
            except Exception as exc:
                data = {
                    'error': exc.__class__.__name__,
                    'message': exc.message if hasattr(exc, 'message') else str(exc)
                }
                tb = format_tb(exc)
                if tb:
                    data['stacktrace'] = tb

                return web.json_response(data, status=500)

        @routes.post('/guard/enable')
        async def guard_enable(request):
            self.set_recording(True)
            return ok()

        @routes.post('/guard/disable')
        async def guard_disable(request):
            self.set_recording(False)
            return ok()

        @routes.get('/guard/status')
        async def guard_status(request):
            return ok({'enabled': self.is_recording_enabled()})

        asyncio.set_event_loop(asyncio.new_event_loop())  # need to create new event loop in new thread
        app = web.Application()
        app.add_routes(routes)
        app.middlewares.append(errors_handler_middleware)

        web.run_app(app,
                    host=self.addr[0],
                    port=self.addr[1],
                    handle_signals=False)  # handle_signals=True doesn't work in separate thread