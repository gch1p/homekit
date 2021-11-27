#!/usr/bin/env python3
import os

from typing import Optional
from aiohttp import web
from aiohttp.web_exceptions import (
    HTTPNotFound
)
from home.config import config
from home.util import parse_addr, stringify, format_tb
from home.sound import (
    amixer,
    Recorder,
    RecordStatus,
    RecordStorage
)


"""
This script must be run as root as it runs arecord.

This script implements HTTP API for amixer and arecord.
"""


# some global variables
# ---------------------

recorder: Optional[Recorder]
routes = web.RouteTableDef()
storage: Optional[RecordStorage]


# common http funcs & helpers
# ---------------------------

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


def ok(data=None):
    if data is None:
        data = 1
    response = {'response': data}
    return web.json_response(response, dumps=stringify)


# recording methods
# -----------------

@routes.get('/record/')
async def do_record(request):
    duration = int(request.query['duration'])
    max = Recorder.get_max_record_time()*15
    if not 0 < duration <= max:
        raise ValueError(f'invalid duration: max duration is {max}')

    record_id = recorder.record(duration)
    return ok({'id': record_id})


@routes.get('/record/info/{id}/')
async def record_info(request):
    record_id = int(request.match_info['id'])
    info = recorder.get_info(record_id)
    return ok(info.as_dict())


@routes.get('/record/forget/{id}/')
async def record_forget(request):
    record_id = int(request.match_info['id'])

    info = recorder.get_info(record_id)
    assert info.status in (RecordStatus.FINISHED, RecordStatus.ERROR), f"can't forget: record status is {info.status}"

    recorder.forget(record_id)
    return ok()


@routes.get('/record/download/{id}/')
async def record_download(request):
    record_id = int(request.match_info['id'])

    info = recorder.get_info(record_id)
    assert info.status == RecordStatus.FINISHED, f"record status is {info.status}"

    return web.FileResponse(info.file.path)


@routes.get('/storage/list/')
async def storage_list(request):
    extended = 'extended' in request.query and int(request.query['extended']) == 1

    files = storage.getfiles(as_objects=extended)
    if extended:
        files = list(map(lambda file: file.__dict__(), files))

    return ok({
        'files': files
    })


@routes.get('/storage/delete/')
async def storage_delete(request):
    file_id = request.query['file_id']
    file = storage.find(file_id)
    if not file:
        raise ValueError(f'file {file} not found')

    storage.delete(file)
    return ok()


@routes.get('/storage/download/')
async def storage_download(request):
    file_id = request.query['file_id']
    file = storage.find(file_id)
    if not file:
        raise ValueError(f'file {file} not found')

    return web.FileResponse(file.path)


# ALSA mixer methods
# ------------------

def _amixer_control_response(control):
    info = amixer.get(control)
    caps = amixer.get_caps(control)
    return ok({
        'caps': caps,
        'info': info
    })


@routes.get('/amixer/get-all/')
async def amixer_get_all(request):
    controls_info = amixer.get_all()
    return ok(controls_info)


@routes.get('/amixer/get/{control}/')
async def amixer_get(request):
    control = request.match_info['control']
    if not amixer.has_control(control):
        raise ValueError(f'invalid control: {control}')

    return _amixer_control_response(control)


@routes.get('/amixer/{op:mute|unmute|cap|nocap}/{control}/')
async def amixer_set(request):
    op = request.match_info['op']
    control = request.match_info['control']
    if not amixer.has_control(control):
        raise ValueError(f'invalid control: {control}')

    f = getattr(amixer, op)
    f(control)

    return _amixer_control_response(control)


@routes.get('/amixer/{op:incr|decr}/{control}/')
async def amixer_volume(request):
    op = request.match_info['op']
    control = request.match_info['control']
    if not amixer.has_control(control):
        raise ValueError(f'invalid control: {control}')

    def get_step() -> Optional[int]:
        if 'step' in request.query:
            step = int(request.query['step'])
            if not 1 <= step <= 50:
                raise ValueError('invalid step value')
            return step
        return None

    f = getattr(amixer, op)
    f(control, step=get_step())

    return _amixer_control_response(control)


# entry point
# -----------

if __name__ == '__main__':
    if not os.getegid() == 0:
        raise RuntimeError("Must be run as root.")

    config.load('sound_node')

    storage = RecordStorage(config['node']['storage'])

    recorder = Recorder(storage=storage)
    recorder.start_thread()

    # start http server
    host, port = parse_addr(config['node']['listen'])
    app = web.Application()
    app.add_routes(routes)
    app.middlewares.append(errors_handler_middleware)

    web.run_app(app,
                host=host,
                port=port,
                handle_signals=True)
