#!/usr/bin/env python3
import logging
import os
import re
import asyncio
import time
import shutil
import home.telegram.aio as telegram

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from home.config import config
from home.util import parse_addr
from home import http
from home.database.sqlite import SQLiteBase
from home.camera import util as camutil

from enum import Enum
from typing import Optional, Union, List, Tuple
from datetime import datetime, timedelta
from functools import cmp_to_key


class TimeFilterType(Enum):
    FIX = 'fix'
    MOTION = 'motion'


class TelegramLinkType(Enum):
    FRAGMENT = 'fragment'
    ORIGINAL_FILE = 'original_file'


def valid_recording_name(filename: str) -> bool:
    return filename.startswith('record_') and filename.endswith('.mp4')


def filename_to_datetime(filename: str) -> datetime:
    filename = os.path.basename(filename).replace('record_', '').replace('.mp4', '')
    return datetime.strptime(filename, datetime_format)


# ipcam database
# --------------

class IPCamServerDatabase(SQLiteBase):
    SCHEMA = 3

    def __init__(self):
        super().__init__()

    def schema_init(self, version: int) -> None:
        cursor = self.cursor()

        if version < 1:
            # timestamps
            cursor.execute("""CREATE TABLE IF NOT EXISTS timestamps (
                camera INTEGER PRIMARY KEY,
                fix_time INTEGER NOT NULL,
                motion_time INTEGER NOT NULL
            )""")
            for cam in config['camera'].keys():
                self.add_camera(cam)

        if version < 2:
            # motion_failures
            cursor.execute("""CREATE TABLE IF NOT EXISTS motion_failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera INTEGER NOT NULL,
                filename TEXT NOT NULL
            )""")

        if version < 3:
            cursor.execute("ALTER TABLE motion_failures ADD COLUMN message TEXT NOT NULL DEFAULT ''")

        self.commit()

    def add_camera(self, camera: int):
        self.cursor().execute("INSERT INTO timestamps (camera, fix_time, motion_time) VALUES (?, ?, ?)",
                              (camera, 0, 0))
        self.commit()

    def add_motion_failure(self,
                           camera: int,
                           filename: str,
                           message: Optional[str]):
        self.cursor().execute("INSERT INTO motion_failures (camera, filename, message) VALUES (?, ?, ?)",
                              (camera, filename, message or ''))
        self.commit()

    def get_all_timestamps(self):
        cur = self.cursor()
        data = {}

        cur.execute("SELECT camera, fix_time, motion_time FROM timestamps")
        for cam, fix_time, motion_time in cur.fetchall():
            data[int(cam)] = {
                'fix': int(fix_time),
                'motion': int(motion_time)
            }

        return data

    def set_timestamp(self,
                      camera: int,
                      time_type: TimeFilterType,
                      time: Union[int, datetime]):
        cur = self.cursor()
        if isinstance(time, datetime):
            time = int(time.timestamp())
        cur.execute(f"UPDATE timestamps SET {time_type.value}_time=? WHERE camera=?", (time, camera))
        self.commit()

    def get_timestamp(self,
                      camera: int,
                      time_type: TimeFilterType) -> int:
        cur = self.cursor()
        cur.execute(f"SELECT {time_type.value}_time FROM timestamps WHERE camera=?", (camera,))
        return int(cur.fetchone()[0])


# ipcam web api
# -------------

class IPCamWebServer(http.HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.get('/api/recordings/{name}', self.get_camera_recordings)
        self.get('/api/recordings/{name}/download/{file}', self.download_recording)
        self.get('/api/camera/list', self.camlist)
        self.get('/api/timestamp/{name}/{type}', self.get_timestamp)
        self.get('/api/timestamp/all', self.get_all_timestamps)

        self.post('/api/debug/migrate-mtimes', self.debug_migrate_mtimes)
        self.post('/api/debug/fix', self.debug_fix)
        self.post('/api/debug/cleanup', self.debug_cleanup)
        self.post('/api/timestamp/{name}/{type}', self.set_timestamp)

        self.post('/api/motion/done/{name}', self.submit_motion)
        self.post('/api/motion/fail/{name}', self.submit_motion_failure)

    async def get_camera_recordings(self, req):
        cam = int(req.match_info['name'])
        try:
            filter = TimeFilterType(req.query['filter'])
        except KeyError:
            filter = None

        files = get_recordings_files(cam, filter)

        return self.ok({'files': files})

    async def download_recording(self, req: http.Request):
        cam = int(req.match_info['name'])
        file = req.match_info['file']

        fullpath = os.path.join(config['camera'][cam]['recordings_path'], file)
        if not os.path.isfile(fullpath):
            raise ValueError(f'file "{fullpath}" does not exists')

        return http.FileResponse(fullpath)

    async def camlist(self, req: http.Request):
        return self.ok(config['camera'])

    async def submit_motion(self, req: http.Request):
        data = await req.post()

        camera = int(req.match_info['name'])
        timecodes = data['timecodes']
        filename = data['filename']

        time = filename_to_datetime(filename)

        try:
            if timecodes != '':
                fragments = camutil.dvr_scan_timecodes(timecodes)
                asyncio.ensure_future(process_fragments(camera, filename, fragments))

            db.set_timestamp(camera, TimeFilterType.MOTION, time)
            return self.ok()

        except camutil.DVRScanInvalidTimecodes as e:
            db.add_motion_failure(camera, filename, str(e))
            db.set_timestamp(camera, TimeFilterType.MOTION, time)
            return self.ok('invalid timecodes')

    async def submit_motion_failure(self, req: http.Request):
        camera = int(req.match_info['name'])

        data = await req.post()
        filename = data['filename']
        message = data['message']

        db.add_motion_failure(camera, filename, message)
        db.set_timestamp(camera, TimeFilterType.MOTION, filename_to_datetime(filename))

        return self.ok()

    async def debug_migrate_mtimes(self, req: http.Request):
        written = {}
        for cam in config['camera'].keys():
            confdir = os.path.join(os.getenv('HOME'), '.config', f'video-util-{cam}')
            for time_type in TimeFilterType:
                txt_file = os.path.join(confdir, f'{time_type.value}_mtime')
                if os.path.isfile(txt_file):
                    with open(txt_file, 'r') as fd:
                        data = fd.read()
                        db.set_timestamp(cam, time_type, int(data.strip()))

                        if cam not in written:
                            written[cam] = []
                        written[cam].append(time_type)

        return self.ok({'written': written})

    async def debug_fix(self, req: http.Request):
        asyncio.ensure_future(fix_job())
        return self.ok()

    async def debug_cleanup(self, req: http.Request):
        asyncio.ensure_future(cleanup_job())
        return self.ok()

    async def set_timestamp(self, req: http.Request):
        cam, time_type, time = self._getset_timestamp_params(req, need_time=True)
        db.set_timestamp(cam, time_type, time)
        return self.ok()

    async def get_timestamp(self, req: http.Request):
        cam, time_type = self._getset_timestamp_params(req)
        return self.ok(db.get_timestamp(cam, time_type))

    async def get_all_timestamps(self, req: http.Request):
        return self.ok(db.get_all_timestamps())

    @staticmethod
    def _getset_timestamp_params(req: http.Request, need_time=False):
        values = []

        cam = int(req.match_info['name'])
        assert cam in config['camera'], 'invalid camera'

        values.append(cam)
        values.append(TimeFilterType(req.match_info['type']))

        if need_time:
            time = req.query['time']
            if time.startswith('record_'):
                time = filename_to_datetime(time)
            elif time.isnumeric():
                time = int(time)
            else:
                raise ValueError('invalid time')
            values.append(time)

        return values


# other global stuff
# ------------------

def open_database():
    global db
    db = IPCamServerDatabase()

    # update cams list in database, if needed
    cams = db.get_all_timestamps().keys()
    for cam in config['camera']:
        if cam not in cams:
            db.add_camera(cam)


def get_recordings_path(cam: int) -> str:
    return config['camera'][cam]['recordings_path']


def get_motion_path(cam: int) -> str:
    return config['camera'][cam]['motion_path']


def get_recordings_files(cam: int,
                         time_filter_type: Optional[TimeFilterType] = None) -> List[dict]:
    from_time = 0
    to_time = int(time.time())

    if time_filter_type:
        from_time = db.get_timestamp(cam, time_filter_type)
        if time_filter_type == TimeFilterType.MOTION:
            to_time = db.get_timestamp(cam, TimeFilterType.FIX)

    from_time = datetime.fromtimestamp(from_time)
    to_time = datetime.fromtimestamp(to_time)

    recdir = get_recordings_path(cam)
    files = [{
        'name': file,
        'size': os.path.getsize(os.path.join(recdir, file))}
             for file in os.listdir(recdir)
             if valid_recording_name(file) and from_time < filename_to_datetime(file) <= to_time]
    files.sort(key=lambda file: file['name'])

    if files:
        last = files[len(files)-1]
        fullpath = os.path.join(recdir, last['name'])
        if camutil.has_handle(fullpath):
            logger.debug(f'get_recordings_files: file {fullpath} has opened handle, ignoring it')
            files.pop()

    return files


async def process_fragments(camera: int,
                            filename: str,
                            fragments: List[Tuple[int, int]]) -> None:
    time = filename_to_datetime(filename)

    rec_dir = get_recordings_path(camera)
    motion_dir = get_motion_path(camera)
    if not os.path.exists(motion_dir):
        os.mkdir(motion_dir)

    for fragment in fragments:
        start, end = fragment

        start -= config['motion']['padding']
        end += config['motion']['padding']

        if start < 0:
            start = 0

        duration = end - start

        dt1 = (time + timedelta(seconds=start)).strftime(datetime_format)
        dt2 = (time + timedelta(seconds=end)).strftime(datetime_format)

        await camutil.ffmpeg_cut(input=os.path.join(rec_dir, filename),
                                 output=os.path.join(motion_dir, f'{dt1}__{dt2}.mp4'),
                                 start_pos=start,
                                 duration=duration)

    if fragments and 'telegram' in config['motion'] and config['motion']['telegram']:
        asyncio.ensure_future(motion_notify_tg(camera, filename, fragments))


async def motion_notify_tg(camera: int,
                           filename: str,
                           fragments: List[Tuple[int, int]]):
    dt_file = filename_to_datetime(filename)
    fmt = '%H:%M:%S'

    text = f'Camera: <b>{camera}</b>\n'
    text += f'Original file: <b>{filename}</b> '
    text += _tg_links(TelegramLinkType.ORIGINAL_FILE, camera, filename)

    for start, end in fragments:
        start -= config['motion']['padding']
        end += config['motion']['padding']

        if start < 0:
            start = 0

        duration = end - start
        if duration < 0:
            duration = 0

        dt1 = dt_file + timedelta(seconds=start)
        dt2 = dt_file + timedelta(seconds=end)

        text += f'\nFragment: <b>{duration}s</b>, {dt1.strftime(fmt)}-{dt2.strftime(fmt)} '
        text += _tg_links(TelegramLinkType.FRAGMENT, camera, f'{dt1.strftime(datetime_format)}__{dt2.strftime(datetime_format)}.mp4')

    await telegram.send_message(text)


def _tg_links(link_type: TelegramLinkType,
              camera: int,
              file: str) -> str:
    links = []
    for link_name, link_template in config['telegram'][f'{link_type.value}_url_templates']:
        link = link_template.replace('{camera}', str(camera)).replace('{file}', file)
        links.append(f'<a href="{link}">{link_name}</a>')
    return ' '.join(links)


async def fix_job() -> None:
    global fix_job_running
    logger.debug('fix_job: starting')

    if fix_job_running:
        logger.error('fix_job: already running')
        return

    try:
        fix_job_running = True
        for cam in config['camera'].keys():
            files = get_recordings_files(cam, TimeFilterType.FIX)
            if not files:
                logger.debug(f'fix_job: no files for camera {cam}')
                continue

            logger.debug(f'fix_job: got %d files for camera {cam}' % (len(files),))

            for file in files:
                fullpath = os.path.join(get_recordings_path(cam), file['name'])
                await camutil.ffmpeg_recreate(fullpath)
                timestamp = filename_to_datetime(file['name'])
                if timestamp:
                    db.set_timestamp(cam, TimeFilterType.FIX, timestamp)

    finally:
        fix_job_running = False


async def cleanup_job() -> None:
    def fn2dt(name: str) -> datetime:
        name = os.path.basename(name)

        if name.startswith('record_'):
            return datetime.strptime(re.match(r'record_(.*?)\.mp4', name).group(1), datetime_format)

        m = re.match(rf'({datetime_format_re})__{datetime_format_re}\.mp4', name)
        if m:
            return datetime.strptime(m.group(1), datetime_format)

        raise ValueError(f'unrecognized filename format: {name}')

    def compare(i1: str, i2: str) -> int:
        dt1 = fn2dt(i1)
        dt2 = fn2dt(i2)

        if dt1 < dt2:
            return -1
        elif dt1 > dt2:
            return 1
        else:
            return 0

    global cleanup_job_running
    logger.debug('cleanup_job: starting')

    if cleanup_job_running:
        logger.error('cleanup_job: already running')
        return

    try:
        cleanup_job_running = True

        gb = float(1 << 30)
        for storage in config['storages']:
            if os.path.exists(storage['mountpoint']):
                total, used, free = shutil.disk_usage(storage['mountpoint'])
                free_gb = free // gb
                if free_gb < config['cleanup_min_gb']:
                    # print(f"{storage['mountpoint']}: free={free}, free_gb={free_gb}")
                    cleaned = 0
                    files = []
                    for cam in storage['cams']:
                        for _dir in (config['camera'][cam]['recordings_path'], config['camera'][cam]['motion_path']):
                            files += list(map(lambda file: os.path.join(_dir, file), os.listdir(_dir)))
                        files = list(filter(lambda path: os.path.isfile(path) and path.endswith('.mp4'), files))
                        files.sort(key=cmp_to_key(compare))

                    for file in files:
                        size = os.stat(file).st_size
                        try:
                            os.unlink(file)
                            cleaned += size
                        except OSError as e:
                            logger.exception(e)
                        if (free + cleaned) // gb >= config['cleanup_min_gb']:
                            break
            else:
                logger.error(f"cleanup_job: {storage['mountpoint']} not found")
    finally:
        cleanup_job_running = False


fix_job_running = False
cleanup_job_running = False

datetime_format = '%Y-%m-%d-%H.%M.%S'
datetime_format_re = r'\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}.\d{2}'
db: Optional[IPCamServerDatabase] = None
server: Optional[IPCamWebServer] = None
logger = logging.getLogger(__name__)


# start of the program
# --------------------

if __name__ == '__main__':
    config.load('ipcam_server')

    open_database()

    loop = asyncio.get_event_loop()

    try:
        if config['fix_enabled']:
            scheduler = AsyncIOScheduler(event_loop=loop)
            scheduler.add_job(fix_job, 'interval', seconds=config['fix_interval'])
            scheduler.add_job(cleanup_job, 'interval', seconds=config['cleanup_interval'])
            scheduler.start()
    except KeyError:
        pass

    server = IPCamWebServer(parse_addr(config['server']['listen']))
    server.run()
