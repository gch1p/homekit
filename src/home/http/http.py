import logging
import asyncio

from aiohttp import web
from aiohttp.web_exceptions import HTTPNotFound

from ..util import stringify, format_tb, Addr


_logger = logging.getLogger(__name__)


@web.middleware
async def errors_handler_middleware(request, handler):
    try:
        response = await handler(request)
        return response

    except HTTPNotFound:
        return web.json_response({'error': 'not found'}, status=404)

    except Exception as exc:
        _logger.exception(exc)
        data = {
            'error': exc.__class__.__name__,
            'message': exc.message if hasattr(exc, 'message') else str(exc)
        }
        tb = format_tb(exc)
        if tb:
            data['stacktrace'] = tb

        return web.json_response(data, status=500)


def serve(addr: Addr, route_table: web.RouteTableDef, handle_signals: bool = True):
    app = web.Application()
    app.add_routes(route_table)
    app.middlewares.append(errors_handler_middleware)

    host, port = addr

    web.run_app(app,
                host=host,
                port=port,
                handle_signals=handle_signals)


def routes() -> web.RouteTableDef:
    return web.RouteTableDef()


def ok(data=None):
    if data is None:
        data = 1
    response = {'response': data}
    return web.json_response(response, dumps=stringify)


class HTTPServer:
    def __init__(self, addr: Addr, handle_errors=True):
        self.addr = addr
        self.app = web.Application()
        self.logger = logging.getLogger(self.__class__.__name__)

        if handle_errors:
            self.app.middlewares.append(errors_handler_middleware)

    def _add_route(self,
                   method: str,
                   path: str,
                   handler: callable):
        self.app.router.add_routes([getattr(web, method)(path, handler)])

    def get(self, path, handler):
        self._add_route('get', path, handler)

    def post(self, path, handler):
        self._add_route('post', path, handler)

    def run(self, event_loop=None, handle_signals=True):
        if not event_loop:
            event_loop = asyncio.get_event_loop()

        runner = web.AppRunner(self.app, handle_signals=handle_signals)
        event_loop.run_until_complete(runner.setup())

        host, port = self.addr
        site = web.TCPSite(runner, host=host, port=port)
        event_loop.run_until_complete(site.start())

        self.logger.info(f'Server started at http://{host}:{port}')

        event_loop.run_forever()

    def ok(self, data=None):
        return ok(data)