from .. import http
from .record import Recorder
from .types import RecordStatus
from .storage import RecordStorage


class MediaNodeServer(http.HTTPServer):
    recorder: Recorder
    storage: RecordStorage

    def __init__(self,
                 recorder: Recorder,
                 storage: RecordStorage,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.recorder = recorder
        self.storage = storage

        self.get('/record/', self.do_record)
        self.get('/record/info/{id}/', self.record_info)
        self.get('/record/forget/{id}/', self.record_forget)
        self.get('/record/download/{id}/', self.record_download)

        self.get('/storage/list/', self.storage_list)
        self.get('/storage/delete/', self.storage_delete)
        self.get('/storage/download/', self.storage_download)

    async def do_record(self, request: http.Request):
        duration = int(request.query['duration'])
        max = Recorder.get_max_record_time()*15
        if not 0 < duration <= max:
            raise ValueError(f'invalid duration: max duration is {max}')

        record_id = self.recorder.record(duration)
        return http.ok({'id': record_id})

    async def record_info(self, request: http.Request):
        record_id = int(request.match_info['id'])
        info = self.recorder.get_info(record_id)
        return http.ok(info.as_dict())

    async def record_forget(self, request: http.Request):
        record_id = int(request.match_info['id'])

        info = self.recorder.get_info(record_id)
        assert info.status in (RecordStatus.FINISHED, RecordStatus.ERROR), f"can't forget: record status is {info.status}"

        self.recorder.forget(record_id)
        return http.ok()

    async def record_download(self, request: http.Request):
        record_id = int(request.match_info['id'])

        info = self.recorder.get_info(record_id)
        assert info.status == RecordStatus.FINISHED, f"record status is {info.status}"

        return http.FileResponse(info.file.path)

    async def storage_list(self, request: http.Request):
        extended = 'extended' in request.query and int(request.query['extended']) == 1

        files = self.storage.getfiles(as_objects=extended)
        if extended:
            files = list(map(lambda file: file.__dict__(), files))

        return http.ok({
            'files': files
        })

    async def storage_delete(self, request: http.Request):
        file_id = request.query['file_id']
        file = self.storage.find(file_id)
        if not file:
            raise ValueError(f'file {file} not found')

        self.storage.delete(file)
        return http.ok()

    async def storage_download(self, request):
        file_id = request.query['file_id']
        file = self.storage.find(file_id)
        if not file:
            raise ValueError(f'file {file} not found')

        return http.FileResponse(file.path)
