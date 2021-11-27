import requests
import logging
import shutil

from ..util import Addr
from ..api.errors import ApiResponseError
from typing import Optional, Union
from .record import RecordFile


class SoundNodeClient:
    def __init__(self, addr: Addr):
        self.endpoint = f'http://{addr[0]}:{addr[1]}'
        self.logger = logging.getLogger(self.__class__.__name__)

    def amixer_get_all(self):
        return self._call('amixer/get-all/')

    def amixer_get(self, control: str):
        return self._call(f'amixer/get/{control}/')

    def amixer_incr(self, control: str, step: Optional[int] = None):
        params = {'step': step} if step is not None else None
        return self._call(f'amixer/incr/{control}/', params=params)

    def amixer_decr(self, control: str, step: Optional[int] = None):
        params = {'step': step} if step is not None else None
        return self._call(f'amixer/decr/{control}/', params=params)

    def amixer_mute(self, control: str):
        return self._call(f'amixer/mute/{control}/')

    def amixer_unmute(self, control: str):
        return self._call(f'amixer/unmute/{control}/')

    def amixer_cap(self, control: str):
        return self._call(f'amixer/cap/{control}/')

    def amixer_nocap(self, control: str):
        return self._call(f'amixer/nocap/{control}/')

    def record(self, duration: int):
        return self._call('record/', params={"duration": duration})

    def record_info(self, record_id: int):
        return self._call(f'record/info/{record_id}/')

    def record_forget(self, record_id: int):
        return self._call(f'record/forget/{record_id}/')

    def record_download(self, record_id: int, output: str):
        return self._call(f'record/download/{record_id}/', save_to=output)

    def storage_list(self, extended=False, as_objects=False) -> Union[list[str], list[dict], list[RecordFile]]:
        r = self._call('storage/list/', params={'extended': int(extended)})
        files = r['files']
        if as_objects:
            return self.record_list_from_serialized(files)
        return files

    @staticmethod
    def record_list_from_serialized(files: Union[list[str], list[dict]]):
        new_files = []
        for f in files:
            kwargs = {'remote': True}
            if isinstance(f, dict):
                name = f['filename']
                kwargs['remote_filesize'] = f['filesize']
            else:
                name = f
            item = RecordFile(name, **kwargs)
            new_files.append(item)
        return new_files

    def storage_delete(self, file_id: str):
        return self._call('storage/delete/', params={'file_id': file_id})

    def storage_download(self, file_id: str, output: str):
        return self._call('storage/download/', params={'file_id': file_id}, save_to=output)

    def _call(self,
              method: str,
              params: dict = None,
              save_to: Optional[str] = None):

        kwargs = {}
        if isinstance(params, dict):
            kwargs['params'] = params
        if save_to:
            kwargs['stream'] = True

        url = f'{self.endpoint}/{method}'
        self.logger.debug(f'calling {url}, kwargs: {kwargs}')

        r = requests.get(url, **kwargs)
        if r.status_code != 200:
            response = r.json()
            raise ApiResponseError(status_code=r.status_code,
                                   error_type=response['error'],
                                   error_message=response['message'] or None,
                                   error_stacktrace=response['stacktrace'] if 'stacktrace' in response else None)

        if save_to:
            r.raise_for_status()
            with open(save_to, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
            return True

        return r.json()['response']
