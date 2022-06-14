import os
import re
import shutil
import logging

from typing import Optional, Union
from datetime import datetime
from ..util import strgen

logger = logging.getLogger(__name__)


# record file
# -----------

class RecordFile:
    EXTENSION = None

    start_time: Optional[datetime]
    stop_time: Optional[datetime]
    record_id: Optional[int]
    name: str
    file_id: Optional[str]
    remote: bool
    remote_filesize: int
    storage_root: str

    human_date_dmt = '%d.%m.%y'
    human_time_fmt = '%H:%M:%S'

    @staticmethod
    def create(filename: str, *args, **kwargs):
        if filename.endswith(f'.{SoundRecordFile.EXTENSION}'):
            return SoundRecordFile(filename, *args, **kwargs)
        elif filename.endswith(f'.{CameraRecordFile.EXTENSION}'):
            return CameraRecordFile(filename, *args, **kwargs)
        else:
            raise RuntimeError(f'unsupported file extension: {filename}')

    def __init__(self, filename: str, remote=False, remote_filesize=None, storage_root='/'):
        if self.EXTENSION is None:
            raise RuntimeError('this is abstract class')

        self.name = filename
        self.storage_root = storage_root

        self.remote = remote
        self.remote_filesize = remote_filesize

        m = re.match(r'^(\d{6}-\d{6})_(\d{6}-\d{6})_id(\d+)(_\w+)?\.'+self.EXTENSION+'$', filename)
        if m:
            self.start_time = datetime.strptime(m.group(1), RecordStorage.time_fmt)
            self.stop_time = datetime.strptime(m.group(2), RecordStorage.time_fmt)
            self.record_id = int(m.group(3))
            self.file_id = (m.group(1) + '_' + m.group(2)).replace('-', '_')
        else:
            logger.warning(f'unexpected filename: {filename}')
            self.start_time = None
            self.stop_time = None
            self.record_id = None
            self.file_id = None

    @property
    def path(self):
        if self.remote:
            return RuntimeError('remote recording, can\'t get real path')

        return os.path.realpath(os.path.join(
            self.storage_root, self.name
        ))

    @property
    def start_humantime(self) -> str:
        if self.start_time is None:
            return '?'
        fmt = f'{RecordFile.human_date_dmt} {RecordFile.human_time_fmt}'
        return self.start_time.strftime(fmt)

    @property
    def stop_humantime(self) -> str:
        if self.stop_time is None:
            return '?'
        fmt = RecordFile.human_time_fmt
        if self.start_time.date() != self.stop_time.date():
            fmt = f'{RecordFile.human_date_dmt} {fmt}'
        return self.stop_time.strftime(fmt)

    @property
    def start_unixtime(self) -> int:
        if self.start_time is None:
            return 0
        return int(self.start_time.timestamp())

    @property
    def stop_unixtime(self) -> int:
        if self.stop_time is None:
            return 0
        return int(self.stop_time.timestamp())

    @property
    def filesize(self):
        if self.remote:
            if self.remote_filesize is None:
                raise RuntimeError('file is remote and remote_filesize is not set')
            return self.remote_filesize
        return os.path.getsize(self.path)

    def __dict__(self) -> dict:
        return {
            'start_unixtime': self.start_unixtime,
            'stop_unixtime': self.stop_unixtime,
            'filename': self.name,
            'filesize': self.filesize,
            'fileid': self.file_id,
            'record_id': self.record_id or 0,
        }


class PseudoRecordFile(RecordFile):
    EXTENSION = 'null'

    def __init__(self):
        super().__init__('pseudo.null')

    @property
    def filesize(self):
        return 0


class SoundRecordFile(RecordFile):
    EXTENSION = 'mp3'


class CameraRecordFile(RecordFile):
    EXTENSION = 'mp4'


# record storage
# --------------

class RecordStorage:
    EXTENSION = None

    time_fmt = '%d%m%y-%H%M%S'

    def __init__(self, root: str):
        if self.EXTENSION is None:
            raise RuntimeError('this is abstract class')

        self.root = root

    def getfiles(self, as_objects=False) -> Union[list[str], list[RecordFile]]:
        files = []
        for name in os.listdir(self.root):
            path = os.path.join(self.root, name)
            if os.path.isfile(path) and name.endswith(f'.{self.EXTENSION}'):
                files.append(name if not as_objects else RecordFile.create(name, storage_root=self.root))
        return files

    def find(self, file_id: str) -> Optional[RecordFile]:
        for name in os.listdir(self.root):
            if os.path.isfile(os.path.join(self.root, name)) and name.endswith(f'.{self.EXTENSION}'):
                item = RecordFile.create(name, storage_root=self.root)
                if item.file_id == file_id:
                    return item
        return None

    def purge(self):
        files = self.getfiles()
        if files:
            logger = logging.getLogger(self.__name__)
            for f in files:
                try:
                    path = os.path.join(self.root, f)
                    logger.debug(f'purge: deleting {path}')
                    os.unlink(path)
                except OSError as exc:
                    logger.exception(exc)

    def delete(self, file: RecordFile):
        os.unlink(file.path)

    def save(self,
             fn: str,
             record_id: int,
             start_time: int,
             stop_time: int) -> RecordFile:

        start_time_s = datetime.fromtimestamp(start_time).strftime(self.time_fmt)
        stop_time_s = datetime.fromtimestamp(stop_time).strftime(self.time_fmt)

        dst_fn = f'{start_time_s}_{stop_time_s}_id{record_id}'
        if os.path.exists(os.path.join(self.root, dst_fn)):
            dst_fn += strgen(4)
        dst_fn += f'.{self.EXTENSION}'
        dst_path = os.path.join(self.root, dst_fn)

        shutil.move(fn, dst_path)
        return RecordFile.create(dst_fn, storage_root=self.root)


class SoundRecordStorage(RecordStorage):
    EXTENSION = 'mp3'


class ESP32CameraRecordStorage(RecordStorage):
    EXTENSION = 'jpg'  # not used anyway

    def save(self, *args, **kwargs):
        return PseudoRecordFile()