import logging
import shutil
import requests
import json

from typing import Union, Optional
from time import sleep
from enum import Enum
from ..api.errors import ApiResponseError
from ..util import Addr


class FrameSize(Enum):
    UXGA_1600x1200 = 13
    SXGA_1280x1024 = 12
    HD_1280x720 = 11
    XGA_1024x768 = 10
    SVGA_800x600 = 9
    VGA_640x480 = 8
    HVGA_480x320 = 7
    CIF_400x296 = 6
    QVGA_320x240 = 5
    N_240x240 = 4
    HQVGA_240x176 = 3
    QCIF_176x144 = 2
    QQVGA_160x120 = 1
    N_96x96 = 0


class WBMode(Enum):
    AUTO = 0
    SUNNY = 1
    CLOUDY = 2
    OFFICE = 3
    HOME = 4


def _assert_bounds(n: int, min: int, max: int):
    if not min <= n <= max:
        raise ValueError(f'value must be between {min} and {max}')


class WebClient:
    def __init__(self, addr: Addr):
        self.endpoint = f'http://{addr[0]}:{addr[1]}'
        self.logger = logging.getLogger(self.__class__.__name__)
        self.delay = 0
        self.isfirstrequest = True

    def syncsettings(self, settings) -> bool:
        status = self.getstatus()
        self.logger.debug(f'syncsettings: status={status}')

        changed_anything = False

        for name, value in settings.items():
            server_name = name
            if name == 'aec_dsp':
                server_name = 'aec2'

            if server_name not in status:
                # legacy compatibility
                if server_name != 'vflip':
                    self.logger.warning(f'syncsettings: field `{server_name}` not found in camera status')
                    continue

            try:
                # server returns 0 or 1 for bool values
                if type(value) is bool:
                    value = int(value)

                if status[server_name] == value:
                    continue
            except KeyError as exc:
                if name != 'vflip':
                    self.logger.error(exc)

            try:
                # fix for cases like when field is called raw_gma, but method is setrawgma()
                name = name.replace('_', '')

                func = getattr(self, f'set{name}')
                self.logger.debug(f'syncsettings: calling set{name}({value})')

                func(value)

                changed_anything = True
            except AttributeError as exc:
                self.logger.exception(exc)
                self.logger.error(f'syncsettings: method set{name}() not found')

        return changed_anything

    def setdelay(self, delay: int):
        self.delay = delay

    def capture(self, save_to: str):
        self._call('capture', save_to=save_to)

    def getstatus(self):
        return json.loads(self._call('status'))

    def setflash(self, enable: bool):
        self._control('flash', int(enable))

    def setframesize(self, fs: Union[int, FrameSize]):
        if type(fs) is int:
            fs = FrameSize(fs)
        self._control('framesize', fs.value)

    def sethmirror(self, enable: bool):
        self._control('hmirror', int(enable))

    def setvflip(self, enable: bool):
        self._control('vflip', int(enable))

    def setawb(self, enable: bool):
        self._control('awb', int(enable))

    def setawbgain(self, enable: bool):
        self._control('awb_gain', int(enable))

    def setwbmode(self, mode: WBMode):
        self._control('wb_mode', mode.value)

    def setaecsensor(self, enable: bool):
        self._control('aec', int(enable))

    def setaecdsp(self, enable: bool):
        self._control('aec2', int(enable))

    def setagc(self, enable: bool):
        self._control('agc', int(enable))

    def setagcgain(self, gain: int):
        _assert_bounds(gain, 1, 31)
        self._control('agc_gain', gain)

    def setgainceiling(self, gainceiling: int):
        _assert_bounds(gainceiling, 2, 128)
        self._control('gainceiling', gainceiling)

    def setbpc(self, enable: bool):
        self._control('bpc', int(enable))

    def setwpc(self, enable: bool):
        self._control('wpc', int(enable))

    def setrawgma(self, enable: bool):
        self._control('raw_gma', int(enable))

    def setlenscorrection(self, enable: bool):
        self._control('lenc', int(enable))

    def setdcw(self, enable: bool):
        self._control('dcw', int(enable))

    def setcolorbar(self, enable: bool):
        self._control('colorbar', int(enable))

    def setquality(self, q: int):
        _assert_bounds(q, 4, 63)
        self._control('quality', q)

    def setbrightness(self, brightness: int):
        _assert_bounds(brightness, -2, -2)
        self._control('brightness', brightness)

    def setcontrast(self, contrast: int):
        _assert_bounds(contrast, -2, 2)
        self._control('contrast', contrast)

    def setsaturation(self, saturation: int):
        _assert_bounds(saturation, -2, 2)
        self._control('saturation', saturation)

    def _control(self, var: str, value: Union[int, str]):
        self._call('control', params={'var': var, 'val': value})

    def _call(self,
              method: str,
              params: Optional[dict] = None,
              save_to: Optional[str] = None):

        if not self.isfirstrequest and self.delay > 0:
            sleeptime = self.delay / 1000
            self.logger.debug(f'sleeping for {sleeptime}')

            sleep(sleeptime)

        self.isfirstrequest = False

        url = f'{self.endpoint}/{method}'
        self.logger.debug(f'calling {url}, params: {params}')

        kwargs = {}
        if params:
            kwargs['params'] = params
        if save_to:
            kwargs['stream'] = True

        r = requests.get(url, **kwargs)
        if r.status_code != 200:
            raise ApiResponseError(status_code=r.status_code)

        if save_to:
            r.raise_for_status()
            with open(save_to, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            return True

        return r.text
