import logging
import json
import os.path

from datetime import datetime, timedelta
from typing import Optional

from werkzeug.exceptions import HTTPException
from flask import Flask, request, Response

from ..config import config, is_development_mode
from ..database import BotsDatabase, SensorsDatabase
from ..util import stringify, format_tb
from ..api.types import BotType, TemperatureSensorLocation, SoundSensorLocation
from ..sound import RecordStorage

db: Optional[BotsDatabase] = None
sensors_db: Optional[SensorsDatabase] = None
app = Flask(__name__)
logger = logging.getLogger(__name__)


class AuthError(Exception):
    def __init__(self, message: str):
        super().__init__()
        self.message = message


# api methods
# -----------

@app.route("/")
def hello():
    message = "nothing here, keep lurking"
    if is_development_mode():
        message += ' (dev mode)'
    return message


@app.route('/api/sensors/data/', methods=['GET'])
def sensors_data():
    hours = request.args.get('hours', type=int, default=1)
    sensor = TemperatureSensorLocation(request.args.get('sensor', type=int))

    if hours < 1 or hours > 24:
        raise ValueError('invalid hours value')

    dt_to = datetime.now()
    dt_from = dt_to - timedelta(hours=hours)

    data = sensors_db.get_temperature_recordings(sensor, (dt_from, dt_to))
    return ok(data)


@app.route('/api/sound_sensors/hits/', methods=['GET'])
def get_sound_sensors_hits():
    location = SoundSensorLocation(request.args.get('location', type=int))

    after = request.args.get('after', type=int)
    kwargs = {}
    if after is None:
        last = request.args.get('last', type=int)
        if last is None:
            raise ValueError('you must pass `after` or `last` params')
        else:
            if not 0 < last < 100:
                raise ValueError('invalid last value: must be between 0 and 100')
            kwargs['last'] = last
    else:
        kwargs['after'] = datetime.fromtimestamp(after)

    data = db.get_sound_hits(location, **kwargs)
    return ok(data)


@app.route('/api/sound_sensors/hits/', methods=['POST'])
def post_sound_sensors_hits():
    hits = []
    for hit, count in json.loads(request.form.get('hits', type=str)):
        if not hasattr(SoundSensorLocation, hit.upper()):
            raise ValueError('invalid sensor location')
        if count < 1:
            raise ValueError(f'invalid count: {count}')
        hits.append((SoundSensorLocation[hit.upper()], count))

    db.add_sound_hits(hits, datetime.now())
    return ok()


@app.route('/api/logs/bot-request/', methods=['POST'])
def log_bot_request():
    user_id = request.form.get('user_id', type=int, default=0)
    message = request.form.get('message', type=str, default='')
    bot = BotType(request.form.get('bot', type=int))

    # validate message
    if message.strip() == '':
        raise ValueError('message can\'t be empty')

    # add record to the database
    db.add_request(bot, user_id, message)

    return ok()


@app.route('/api/logs/openwrt/', methods=['POST'])
def log_openwrt():
    logs = request.form.get('logs', type=str, default='')

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

    db.add_openwrt_logs(lines)
    return ok()


@app.route('/api/recordings/list/', methods=['GET'])
def recordings_list():
    extended = request.args.get('extended', type=bool, default=False)
    node = request.args.get('node', type=str)

    root = os.path.join(config['recordings']['directory'], node)
    if not os.path.isdir(root):
        raise ValueError(f'invalid node {node}: no such directory')

    storage = RecordStorage(root)
    files = storage.getfiles(as_objects=extended)
    if extended:
        files = list(map(lambda file: file.__dict__(), files))

    return ok(files)


# internal functions
# ------------------

def ok(data=None) -> Response:
    response = {'result': 'ok'}
    if data is not None:
        response['data'] = data
    return Response(stringify(response),
                    mimetype='application/json')


def err(e) -> Response:
    error = {
        'type': e.__class__.__name__,
        'message': e.message if hasattr(e, 'message') else str(e)
    }
    if is_development_mode():
        tb = format_tb(e)
        if tb:
            error['stacktrace'] = tb
    data = {
        'result': 'error',
        'error': error
    }
    return Response(stringify(data), mimetype='application/json')


def get_token() -> Optional[str]:
    name = 'X-Token'
    if name in request.headers:
        return request.headers[name]

    token = request.args.get('token', default='', type=str)
    if token != '':
        return token

    return None


@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    return err(e), 500


@app.before_request
def validate_token() -> None:
    if request.path.startswith('/api/') and not is_development_mode():
        token = get_token()
        if not token:
            raise AuthError(f'token is missing')

        if token != config['api']['token']:
            raise AuthError('invalid token')


def get_app():
    global db, sensors_db

    config.load('web_api')
    app.config.from_mapping(**config['flask'])

    db = BotsDatabase()
    sensors_db = SensorsDatabase()

    return app
