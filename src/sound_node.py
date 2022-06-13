#!/usr/bin/env python3
import os

from typing import Optional

from home.util import parse_addr
from home.config import config
from home.audio import amixer
from home.media import MediaNodeServer, SoundRecordStorage, SoundRecorder
from home import http


# This script must be run as root as it runs arecord.
# Implements HTTP API for amixer and arecord.
# -------------------------------------------

def _amixer_control_response(control):
    info = amixer.get(control)
    caps = amixer.get_caps(control)
    return http.ok({
        'caps': caps,
        'info': info
    })


class SoundNodeServer(MediaNodeServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.get('/amixer/get-all/', self.amixer_get_all)
        self.get('/amixer/get/{control}/', self.amixer_get)
        self.get('/amixer/{op:mute|unmute|cap|nocap}/{control}/', self.amixer_set)
        self.get('/amixer/{op:incr|decr}/{control}/', self.amixer_volume)

    async def amixer_get_all(self, request: http.Request):
        controls_info = amixer.get_all()
        return self.ok(controls_info)

    async def amixer_get(self, request: http.Request):
        control = request.match_info['control']
        if not amixer.has_control(control):
            raise ValueError(f'invalid control: {control}')

        return _amixer_control_response(control)

    async def amixer_set(self, request: http.Request):
        op = request.match_info['op']
        control = request.match_info['control']
        if not amixer.has_control(control):
            raise ValueError(f'invalid control: {control}')

        f = getattr(amixer, op)
        f(control)

        return _amixer_control_response(control)

    async def amixer_volume(self, request: http.Request):
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


if __name__ == '__main__':
    if not os.getegid() == 0:
        raise RuntimeError("Must be run as root.")

    config.load('sound_node')

    storage = SoundRecordStorage(config['node']['storage'])

    recorder = SoundRecorder(storage=storage)
    recorder.start_thread()

    server = SoundNodeServer(recorder=recorder,
                             storage=storage,
                             addr=parse_addr(config['node']['listen']))
    server.run()
