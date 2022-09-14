#!/usr/bin/env python3
import shutil
import sys
import os
import re
import logging
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..')
    )
])

from functools import cmp_to_key
from datetime import datetime
from pprint import pprint
from src.home.config import config


logger = logging.getLogger(__name__)
datetime_format = '%Y-%m-%d-%H.%M.%S'
datetime_format_re = r'\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}.\d{2}'


def cleanup_job():
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

    gb = float(1 << 30)
    for storage in config['storages']:
        if os.path.exists(storage['mountpoint']):
            total, used, free = shutil.disk_usage(storage['mountpoint'])
            free_gb = free // gb
            if free_gb < config['cleanup_min_gb']:
                # print(f"{storage['mountpoint']}: free={free}, free_gb={free_gb}")
                # continue
                cleaned = 0
                files = []
                for cam in storage['cams']:
                    for _dir in (config['camera'][cam]['recordings_path'], config['camera'][cam]['motion_path']):
                        files += list(map(lambda file: os.path.join(_dir, file), os.listdir(_dir)))
                    files = list(filter(lambda path: os.path.isfile(path) and path.endswith('.mp4'), files))
                    files.sort(key=cmp_to_key(compare))
                    # files = list(sorted(files, key=compare))

                for file in files:
                    size = os.stat(file).st_size
                    try:
                        # os.unlink(file)
                        print(f'unlink {file}')
                        cleaned += size
                    except OSError as e:
                        logger.exception(e)
                    if (free + cleaned) // gb >= config['cleanup_min_gb']:
                        break
        else:
            logger.error(f"cleanup_job: {storage['mountpoint']} not found")


if __name__ == '__main__':
    config.load('ipcam_server')
    cleanup_job()
