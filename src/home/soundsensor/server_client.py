import requests
import logging

from ..util import Addr
from ..api.errors import ApiResponseError


class SoundSensorServerGuardClient:
    def __init__(self, addr: Addr):
        self.endpoint = f'http://{addr[0]}:{addr[1]}'
        self.logger = logging.getLogger(self.__class__.__name__)

    def guard_enable(self):
        return self._call('guard/enable', is_post=True)

    def guard_disable(self):
        return self._call('guard/disable', is_post=True)

    def guard_status(self):
        return self._call('guard/status')

    def _call(self,
              method: str,
              is_post=False):

        url = f'{self.endpoint}/{method}'
        self.logger.debug(f'calling {url}')

        r = requests.get(url) if not is_post else requests.post(url)

        if r.status_code != 200:
            response = r.json()
            raise ApiResponseError(status_code=r.status_code,
                                   error_type=response['error'],
                                   error_message=response['message'] or None,
                                   error_stacktrace=response['stacktrace'] if 'stacktrace' in response else None)

        return r.json()['response']
