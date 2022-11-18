#!/usr/bin/env python3
import asyncio
import json
import os

from datetime import datetime, timedelta

from aiohttp import web
from home import http
from home.util import parse_addr
from home.config import config, is_development_mode
from home.database import BotsDatabase, SensorsDatabase, InverterDatabase
from home.database.inverter_time_formats import *
from home.api.types import BotType, TemperatureSensorLocation, SoundSensorLocation
from home.media import SoundRecordStorage


def strptime_auto(s: str) -> datetime:
    e = None
    for fmt in (FormatTime, FormatDate):
        try:
            return datetime.strptime(s, fmt)
        except ValueError as _e:
            e = _e
    raise e


class AuthError(Exception):
    def __init__(self, message: str):
        super().__init__()
        self.message = message


class WebAPIServer(http.HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.app.middlewares.append(self.validate_auth)

        self.get('/', self.get_index)
        self.get('/sensors/data/', self.GET_sensors_data)
        self.get('/sound_sensors/hits/', self.GET_sound_sensors_hits)
        self.post('/sound_sensors/hits/', self.POST_sound_sensors_hits)

        self.post('/log/bot_request/', self.POST_bot_request_log)
        self.post('/log/openwrt/', self.POST_openwrt_log)

        self.get('/inverter/consumed_energy/', self.GET_consumed_energy)
        self.get('/inverter/grid_consumed_energy/', self.GET_grid_consumed_energy)

        self.get('/recordings/list/', self.GET_recordings_list)

    @staticmethod
    @web.middleware
    async def validate_auth(req: http.Request, handler):
        def get_token() -> str:
            name = 'X-Token'
            if name in req.headers:
                return req.headers[name]

            return req.query['token']

        try:
            token = get_token()
        except KeyError:
            raise AuthError('no token')

        if token != config['api']['token']:
            raise AuthError('invalid token')

        return await handler(req)

    @staticmethod
    async def get_index(req: http.Request):
        message = "nothing here, keep lurking"
        if is_development_mode():
            message += ' (dev mode)'
        return http.Response(text=message, content_type='text/plain')

    async def GET_sensors_data(self, req: http.Request):
        try:
            hours = int(req.query['hours'])
            if hours < 1 or hours > 24:
                raise ValueError('invalid hours value')
        except KeyError:
            hours = 1

        sensor = TemperatureSensorLocation(int(req.query['sensor']))

        dt_to = datetime.now()
        dt_from = dt_to - timedelta(hours=hours)

        db = SensorsDatabase()
        data = db.get_temperature_recordings(sensor, (dt_from, dt_to))
        return self.ok(data)

    async def GET_sound_sensors_hits(self, req: http.Request):
        location = SoundSensorLocation(int(req.query['location']))

        after = int(req.query['after'])
        kwargs = {}
        if after is None:
            last = int(req.query['last'])
            if last is None:
                raise ValueError('you must pass `after` or `last` params')
            else:
                if not 0 < last < 100:
                    raise ValueError('invalid last value: must be between 0 and 100')
                kwargs['last'] = last
        else:
            kwargs['after'] = datetime.fromtimestamp(after)

        data = BotsDatabase().get_sound_hits(location, **kwargs)
        return self.ok(data)

    async def POST_sound_sensors_hits(self, req: http.Request):
        hits = []
        data = await req.post()
        for hit, count in json.loads(data['hits']):
            if not hasattr(SoundSensorLocation, hit.upper()):
                raise ValueError('invalid sensor location')
            if count < 1:
                raise ValueError(f'invalid count: {count}')
            hits.append((SoundSensorLocation[hit.upper()], count))

        BotsDatabase().add_sound_hits(hits, datetime.now())
        return self.ok()

    async def POST_bot_request_log(self, req: http.Request):
        data = await req.post()

        try:
            user_id = int(data['user_id'])
        except KeyError:
            user_id = 0

        try:
            message = data['message']
        except KeyError:
            message = ''

        bot = BotType(int(data['bot']))

        # validate message
        if message.strip() == '':
            raise ValueError('message can\'t be empty')

        # add record to the database
        BotsDatabase().add_request(bot, user_id, message)

        return self.ok()

    async def POST_openwrt_log(self, req: http.Request):
        data = await req.post()

        try:
            logs = data['logs']
        except KeyError:
            logs = ''

        # validate it
        logs = json.loads(logs)
        assert type(logs) is list, "invalid json data (list expected)"

        lines = []
        for line in logs:
            assert type(line) is list, "invalid line type (list expected)"
            assert len(line) == 2, f"expected 2 items in line, got {len(line)}"
            assert type(line[0]) is int, "invalid line[0] type (int expected)"
            assert type(line[1]) is str, "invalid line[1] type (str expected)"

            lines.append((
                datetime.fromtimestamp(line[0]),
                line[1]
            ))

        BotsDatabase().add_openwrt_logs(lines)
        return self.ok()

    async def GET_recordings_list(self, req: http.Request):
        data = await req.post()

        try:
            extended = bool(int(data['extended']))
        except KeyError:
            extended = False

        node = data['node']

        root = os.path.join(config['recordings']['directory'], node)
        if not os.path.isdir(root):
            raise ValueError(f'invalid node {node}: no such directory')

        storage = SoundRecordStorage(root)
        files = storage.getfiles(as_objects=extended)
        if extended:
            files = list(map(lambda file: file.__dict__(), files))

        return self.ok(files)

    @staticmethod
    def _get_inverter_from_to(req: http.Request):
        s_from = req.query['from']
        s_to = req.query['to']

        dt_from = strptime_auto(s_from)

        if s_to == 'now':
            dt_to = datetime.now()
        else:
            dt_to = strptime_auto(s_to)

        return dt_from, dt_to

    async def GET_consumed_energy(self, req: http.Request):
        dt_from, dt_to = self._get_inverter_from_to(req)
        wh = InverterDatabase().get_consumed_energy(dt_from, dt_to)
        return self.ok(wh)

    async def GET_grid_consumed_energy(self, req: http.Request):
        dt_from, dt_to = self._get_inverter_from_to(req)
        wh = InverterDatabase().get_grid_consumed_energy(dt_from, dt_to)
        return self.ok(wh)


# start of the program
# --------------------

if __name__ == '__main__':
    _app_name = 'web_api'
    if is_development_mode():
        _app_name += '_dev'
    config.load(_app_name)

    loop = asyncio.get_event_loop()

    server = WebAPIServer(parse_addr(config['server']['listen']))
    server.run()
