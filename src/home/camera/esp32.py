import logging
import requests
import json
import asyncio
import aioshutil

from io import BytesIO
from functools import partial
from typing import Union, Optional
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
    def __init__(self,
                 addr: Addr):
        self.endpoint = f'http://{addr[0]}:{addr[1]}'
        self.logger = logging.getLogger(self.__class__.__name__)
        self.delay = 0
        self.isfirstrequest = True

    async def syncsettings(self, settings) -> bool:
        status = await self.getstatus()
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

                await func(value)

                changed_anything = True
            except AttributeError as exc:
                self.logger.exception(exc)
                self.logger.error(f'syncsettings: method set{name}() not found')

        return changed_anything

    def setdelay(self, delay: int):
        self.delay = delay

    async def capture(self, output: Optional[str] = None) -> Union[BytesIO, bool]:
        kw = {}
        if output:
            kw['save_to'] = output
        else:
            kw['as_bytes'] = True
        return await self._call('capture', **kw)

    async def getstatus(self):
        return json.loads(await self._call('status'))

    async def setflash(self, enable: bool):
        await self._control('flash', int(enable))

    async def setframesize(self, fs: Union[int, FrameSize]):
        if type(fs) is int:
            fs = FrameSize(fs)
        await self._control('framesize', fs.value)

    async def sethmirror(self, enable: bool):
        await self._control('hmirror', int(enable))

    async def setvflip(self, enable: bool):
        await self._control('vflip', int(enable))

    async def setawb(self, enable: bool):
        await self._control('awb', int(enable))

    async def setawbgain(self, enable: bool):
        await self._control('awb_gain', int(enable))

    async def setwbmode(self, mode: WBMode):
        await self._control('wb_mode', mode.value)

    async def setaecsensor(self, enable: bool):
        await self._control('aec', int(enable))

    async def setaecdsp(self, enable: bool):
        await self._control('aec2', int(enable))

    async def setagc(self, enable: bool):
        await self._control('agc', int(enable))

    async def setagcgain(self, gain: int):
        _assert_bounds(gain, 1, 31)
        await self._control('agc_gain', gain)

    async def setgainceiling(self, gainceiling: int):
        _assert_bounds(gainceiling, 2, 128)
        await self._control('gainceiling', gainceiling)

    async def setbpc(self, enable: bool):
        await self._control('bpc', int(enable))

    async def setwpc(self, enable: bool):
        await self._control('wpc', int(enable))

    async def setrawgma(self, enable: bool):
        await self._control('raw_gma', int(enable))

    async def setlenscorrection(self, enable: bool):
        await self._control('lenc', int(enable))

    async def setdcw(self, enable: bool):
        await self._control('dcw', int(enable))

    async def setcolorbar(self, enable: bool):
        await self._control('colorbar', int(enable))

    async def setquality(self, q: int):
        _assert_bounds(q, 4, 63)
        await self._control('quality', q)

    async def setbrightness(self, brightness: int):
        _assert_bounds(brightness, -2, -2)
        await self._control('brightness', brightness)

    async def setcontrast(self, contrast: int):
        _assert_bounds(contrast, -2, 2)
        await self._control('contrast', contrast)

    async def setsaturation(self, saturation: int):
        _assert_bounds(saturation, -2, 2)
        await self._control('saturation', saturation)

    async def _control(self, var: str, value: Union[int, str]):
        return await self._call('control', params={'var': var, 'val': value})

    async def _call(self,
                    method: str,
                    params: Optional[dict] = None,
                    save_to: Optional[str] = None,
                    as_bytes=False) -> Union[str, bool, BytesIO]:
        loop = asyncio.get_event_loop()

        if not self.isfirstrequest and self.delay > 0:
            sleeptime = self.delay / 1000
            self.logger.debug(f'sleeping for {sleeptime}')

            await asyncio.sleep(sleeptime)

        self.isfirstrequest = False

        url = f'{self.endpoint}/{method}'
        self.logger.debug(f'calling {url}, params: {params}')

        kwargs = {}
        if params:
            kwargs['params'] = params
        if save_to:
            kwargs['stream'] = True

        r = await loop.run_in_executor(None,
                                       partial(requests.get, url, **kwargs))
        if r.status_code != 200:
            raise ApiResponseError(status_code=r.status_code)

        if as_bytes:
            return BytesIO(r.content)

        if save_to:
            r.raise_for_status()
            with open(save_to, 'wb') as f:
                await aioshutil.copyfileobj(r.raw, f)
            return True

        return r.text
