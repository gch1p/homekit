#!/usr/bin/env python3
import asyncio
import time

from home.config import config
from home.media import MediaNodeServer, ESP32CameraRecordStorage, CameraRecorder
from home.camera import CameraType, esp32
from home.util import Addr
from home import http


# Implements HTTP API for a camera.
# ---------------------------------

class ESP32CameraNodeServer(MediaNodeServer):
    def __init__(self, web_addr: Addr, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_settings_sync = 0

        self.web = esp32.WebClient(web_addr)
        self.get('/capture/', self.capture)

    async def capture(self, req: http.Request):
        await self.sync_settings_if_needed()

        try:
            with_flash = int(req.query['with_flash'])
        except KeyError:
            with_flash = 0

        if with_flash:
            await self.web.setflash(True)
            await asyncio.sleep(1)

        bytes = (await self.web.capture()).read()

        if with_flash:
            await self.web.setflash(False)

        res = http.StreamResponse()
        res.content_type = 'image/jpeg'
        res.content_length = len(bytes)

        await res.prepare(req)
        await res.write(bytes)
        await res.write_eof()

        return res

    async def do_record(self, request: http.Request):
        await self.sync_settings_if_needed()

        # sync settings
        return await super().do_record(request)

    async def sync_settings_if_needed(self):
        if self.last_settings_sync != 0 and time.time() - self.last_settings_sync < 300:
            return
        changed = await self.web.syncsettings(config['camera']['settings'])
        if changed:
            self.logger.debug('sync_settings_if_needed: some settings were changed, sleeping for 0.4 sec')
            await asyncio.sleep(0.4)
        self.last_settings_sync = time.time()


if __name__ == '__main__':
    config.load('camera_node')

    recorder_kwargs = {}
    camera_type = CameraType(config['camera']['type'])
    if camera_type == CameraType.ESP32:
        recorder_kwargs['stream_addr'] = config.get_addr('camera.web_addr')  # this is not a mistake, we don't use stream_addr for esp32-cam anymore
        storage = ESP32CameraRecordStorage(config['node']['storage'])
    else:
        raise RuntimeError(f'unsupported camera type {camera_type}')

    recorder = CameraRecorder(storage=storage,
                              camera_type=camera_type,
                              **recorder_kwargs)
    recorder.start_thread()

    server = ESP32CameraNodeServer(
        recorder=recorder,
        storage=storage,
        web_addr=config.get_addr('camera.web_addr'),
        addr=config.get_addr('node.listen'))
    server.run()
