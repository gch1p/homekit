import asyncio
import os.path
import logging
import psutil

from typing import List, Tuple
from ..util import chunks
from ..config import config

_logger = logging.getLogger(__name__)
_temporary_fixing = '.temporary_fixing.mp4'


def _get_ffmpeg_path() -> str:
    return 'ffmpeg' if 'ffmpeg' not in config else config['ffmpeg']['path']


def time2seconds(time: str) -> int:
    time, frac = time.split('.')
    frac = int(frac)

    h, m, s = [int(i) for i in time.split(':')]

    return round(s + m*60 + h*3600 + frac/1000)


async def ffmpeg_recreate(filename: str):
    filedir = os.path.dirname(filename)
    tempname = os.path.join(filedir, _temporary_fixing)
    mtime = os.path.getmtime(filename)

    args = [_get_ffmpeg_path(), '-nostats', '-loglevel', 'error', '-i', filename, '-c', 'copy', '-y', tempname]
    proc = await asyncio.create_subprocess_exec(*args,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        _logger.error(f'fix_timestamps({filename}): ffmpeg returned {proc.returncode}, stderr: {stderr.decode().strip()}')

    if os.path.isfile(tempname):
        os.unlink(filename)
        os.rename(tempname, filename)
        os.utime(filename, (mtime, mtime))
        _logger.info(f'fix_timestamps({filename}): OK')
    else:
        _logger.error(f'fix_timestamps({filename}): temp file \'{tempname}\' does not exists, fix failed')


async def ffmpeg_cut(input: str,
                     output: str,
                     start_pos: int,
                     duration: int):
    args = [_get_ffmpeg_path(), '-nostats', '-loglevel', 'error', '-i', input,
            '-ss', str(start_pos), '-t', str(duration),
            '-c', 'copy', '-y', output]
    proc = await asyncio.create_subprocess_exec(*args,
                                                stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        _logger.error(f'ffmpeg_cut({input}, start_pos={start_pos}, duration={duration}): ffmpeg returned {proc.returncode}, stderr: {stderr.decode().strip()}')
    else:
        _logger.info(f'ffmpeg_cut({input}): OK')


def dvr_scan_timecodes(timecodes: str) -> List[Tuple[int, int]]:
    tc_backup = timecodes

    timecodes = timecodes.split(',')
    if len(timecodes) % 2 != 0:
        raise DVRScanInvalidTimecodes(f'invalid number of timecodes. input: {tc_backup}')

    timecodes = list(map(time2seconds, timecodes))
    timecodes = list(chunks(timecodes, 2))

    # sort out invalid fragments (dvr-scan returns them sometimes, idk why...)
    timecodes = list(filter(lambda f: f[0] < f[1], timecodes))
    if not timecodes:
        raise DVRScanInvalidTimecodes(f'no valid timecodes. input: {tc_backup}')

    # https://stackoverflow.com/a/43600953
    timecodes.sort(key=lambda interval: interval[0])
    merged = [timecodes[0]]
    for current in timecodes:
        previous = merged[-1]
        if current[0] <= previous[1]:
            previous[1] = max(previous[1], current[1])
        else:
            merged.append(current)

    return merged


class DVRScanInvalidTimecodes(Exception):
    pass


def has_handle(fpath):
    for proc in psutil.process_iter():
        try:
            for item in proc.open_files():
                if fpath == item.path:
                    return True
        except Exception:
            pass

    return False