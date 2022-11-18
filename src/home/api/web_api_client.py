import requests
import json
import threading
import logging

from collections import namedtuple
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Callable, Union, List, Tuple, Dict
from requests.auth import HTTPBasicAuth

from .errors import ApiResponseError
from .types import *
from ..config import config
from ..util import stringify
from ..media import RecordFile, MediaNodeClient

logger = logging.getLogger(__name__)


RequestParams = namedtuple('RequestParams', 'params, files, method')


class HTTPMethod(Enum):
    GET = auto()
    POST = auto()


class WebAPIClient:
    token: str
    timeout: Union[float, Tuple[float, float]]
    basic_auth: Optional[HTTPBasicAuth]
    do_async: bool
    async_error_handler: Optional[Callable]
    async_success_handler: Optional[Callable]

    def __init__(self, timeout: Union[float, Tuple[float, float]] = 5):
        self.token = config['api']['token']
        self.timeout = timeout
        self.basic_auth = None
        self.do_async = False
        self.async_error_handler = None
        self.async_success_handler = None

        if 'basic_auth' in config['api']:
            ba = config['api']['basic_auth']
            col = ba.index(':')

            user = ba[:col]
            pw = ba[col+1:]

            logger.debug(f'enabling basic auth: {user}:{pw}')
            self.basic_auth = HTTPBasicAuth(user, pw)

    # api methods
    # -----------

    def log_bot_request(self,
                        bot: BotType,
                        user_id: int,
                        message: str):
        return self._post('log/bot_request/', {
            'bot': bot.value,
            'user_id': str(user_id),
            'message': message
        })

    def log_openwrt(self,
                    lines: List[Tuple[int, str]]):
        return self._post('log/openwrt/', {
            'logs': stringify(lines)
        })

    def get_sensors_data(self,
                         sensor: TemperatureSensorLocation,
                         hours: int):
        data = self._get('sensors/data/', {
            'sensor': sensor.value,
            'hours': hours
        })
        return [(datetime.fromtimestamp(date), temp, hum) for date, temp, hum in data]

    def add_sound_sensor_hits(self,
                              hits: List[Tuple[str, int]]):
        return self._post('sound_sensors/hits/', {
            'hits': stringify(hits)
        })

    def get_sound_sensor_hits(self,
                              location: SoundSensorLocation,
                              after: datetime) -> List[dict]:
        return self._process_sound_sensor_hits_data(self._get('sound_sensors/hits/', {
            'after': int(after.timestamp()),
            'location': location.value
        }))

    def get_last_sound_sensor_hits(self, location: SoundSensorLocation, last: int):
        return self._process_sound_sensor_hits_data(self._get('sound_sensors/hits/', {
            'last': last,
            'location': location.value
        }))

    def recordings_list(self, extended=False, as_objects=False) -> Union[List[str], List[dict], List[RecordFile]]:
        files = self._get('recordings/list/', {'extended': int(extended)})['data']
        if as_objects:
            return MediaNodeClient.record_list_from_serialized(files)
        return files

    def inverter_get_consumed_energy(self, s_from: str, s_to: str):
        return self._get('inverter/consumed_energy/', {
            'from': s_from,
            'to': s_to
        })

    def inverter_get_grid_consumed_energy(self, s_from: str, s_to: str):
        return self._get('inverter/grid_consumed_energy/', {
            'from': s_from,
            'to': s_to
        })

    @staticmethod
    def _process_sound_sensor_hits_data(data: List[dict]) -> List[dict]:
        for item in data:
            item['time'] = datetime.fromtimestamp(item['time'])
        return data

    # internal methods
    # ----------------

    def _get(self, *args, **kwargs):
        return self._call(method=HTTPMethod.GET, *args, **kwargs)

    def _post(self, *args, **kwargs):
        return self._call(method=HTTPMethod.POST, *args, **kwargs)

    def _call(self,
              name: str,
              params: dict,
              method: HTTPMethod,
              files: Optional[Dict[str, str]] = None):
        if not self.do_async:
            return self._make_request(name, params, method, files)
        else:
            t = threading.Thread(target=self._make_request_in_thread, args=(name, params, method, files))
            t.start()
            return None

    def _make_request(self,
                      name: str,
                      params: dict,
                      method: HTTPMethod = HTTPMethod.GET,
                      files: Optional[Dict[str, str]] = None) -> Optional[any]:
        domain = config['api']['host']
        kwargs = {}

        if self.basic_auth is not None:
            kwargs['auth'] = self.basic_auth

        if method == HTTPMethod.GET:
            if files:
                raise RuntimeError('can\'t upload files using GET, please use me properly')
            kwargs['params'] = params
            f = requests.get
        else:
            kwargs['data'] = params
            f = requests.post

        fd = {}
        if files:
            for fname, fpath in files.items():
                fd[fname] = open(fpath, 'rb')
            kwargs['files'] = fd

        try:
            r = f(f'https://{domain}/{name}',
                  headers={'X-Token': self.token},
                  timeout=self.timeout,
                  **kwargs)

            if not r.headers['content-type'].startswith('application/json'):
                raise ApiResponseError(r.status_code, 'TypeError', 'content-type is not application/json')

            data = json.loads(r.text)
            if r.status_code != 200:
                raise ApiResponseError(r.status_code,
                                       data['error']['type'],
                                       data['error']['message'],
                                       data['error']['stacktrace'] if 'stacktrace' in data['error'] else None)

            return data['response'] if 'response' in data else True
        finally:
            for fname, f in fd.items():
                # logger.debug(f'closing file {fname} (fd={f})')
                try:
                    f.close()
                except Exception as exc:
                    logger.exception(exc)
                    pass

    def _make_request_in_thread(self, name, params, method, files):
        try:
            result = self._make_request(name, params, method, files)
            self._report_async_success(result, name, RequestParams(params=params, method=method, files=files))
        except Exception as e:
            logger.exception(e)
            self._report_async_error(e, name, RequestParams(params=params, method=method, files=files))

    def enable_async(self,
                     success_handler: Optional[Callable] = None,
                     error_handler: Optional[Callable] = None):
        self.do_async = True
        if error_handler:
            self.async_error_handler = error_handler
        if success_handler:
            self.async_success_handler = success_handler

    def _report_async_error(self, *args):
        if self.async_error_handler:
            self.async_error_handler(*args)

    def _report_async_success(self, *args):
        if self.async_success_handler:
            self.async_success_handler(*args)