import os
import threading
import logging
import time
import subprocess
import signal

from typing import Optional, List, Dict
from ..util import find_child_processes, Addr
from ..config import config
from .storage import RecordFile, RecordStorage
from .types import RecordStatus
from ..camera.types import CameraType


_history_item_timeout = 7200
_history_cleanup_freq = 3600


class RecordHistoryItem:
    id: int
    request_time: float
    start_time: float
    stop_time: float
    relations: List[int]
    status: RecordStatus
    error: Optional[Exception]
    file: Optional[RecordFile]
    creation_time: float

    def __init__(self, id):
        self.id = id
        self.request_time = 0
        self.start_time = 0
        self.stop_time = 0
        self.relations = []
        self.status = RecordStatus.WAITING
        self.file = None
        self.error = None
        self.creation_time = time.time()

    def add_relation(self, related_id: int):
        self.relations.append(related_id)

    def mark_started(self, start_time: float):
        self.start_time = start_time
        self.status = RecordStatus.RECORDING

    def mark_finished(self, end_time: float, file: RecordFile):
        self.stop_time = end_time
        self.file = file
        self.status = RecordStatus.FINISHED

    def mark_failed(self, error: Exception):
        self.status = RecordStatus.ERROR
        self.error = error

    def as_dict(self) -> dict:
        data = {
            'id': self.id,
            'request_time': self.request_time,
            'status': self.status.value,
            'relations': self.relations,
            'start_time': self.start_time,
            'stop_time': self.stop_time,
        }
        if self.error:
            data['error'] = str(self.error)
        if self.file:
            data['file'] = self.file.__dict__()
        return data


class RecordingNotFoundError(Exception):
    pass


class RecordHistory:
    history: Dict[int, RecordHistoryItem]

    def __init__(self):
        self.history = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add(self, record_id: int):
        self.logger.debug(f'add: record_id={record_id}')

        r = RecordHistoryItem(record_id)
        r.request_time = time.time()

        self.history[record_id] = r

    def delete(self, record_id: int):
        self.logger.debug(f'delete: record_id={record_id}')
        del self.history[record_id]

    def cleanup(self):
        del_ids = []
        for rid, item in self.history.items():
            if item.creation_time < time.time()-_history_item_timeout:
                del_ids.append(rid)
        for rid in del_ids:
            self.delete(rid)

    def __getitem__(self, key):
        if key not in self.history:
            raise RecordingNotFoundError()

        return self.history[key]

    def __setitem__(self, key, value):
        raise NotImplementedError('setting history item this way is prohibited')

    def __contains__(self, key):
        return key in self.history


class Recording:
    RECORDER_PROGRAM = None

    start_time: float
    stop_time: float
    duration: int
    record_id: int
    recorder_program_pid: Optional[int]
    process: Optional[subprocess.Popen]

    g_record_id = 1

    def __init__(self):
        if self.RECORDER_PROGRAM is None:
            raise RuntimeError('this is abstract class')

        self.start_time = 0
        self.stop_time = 0
        self.duration = 0
        self.process = None
        self.recorder_program_pid = None
        self.record_id = Recording.next_id()
        self.logger = logging.getLogger(self.__class__.__name__)

    def is_started(self) -> bool:
        return self.start_time > 0 and self.stop_time > 0

    def is_waiting(self):
        return self.duration > 0

    def ask_for(self, duration) -> int:
        overtime = 0
        orig_duration = duration

        if self.is_started():
            already_passed = time.time() - self.start_time
            max_duration = Recorder.get_max_record_time() - already_passed
            self.logger.debug(f'ask_for({orig_duration}): recording is in progress, already passed {already_passed}s, max_duration set to {max_duration}')
        else:
            max_duration = Recorder.get_max_record_time()

        if duration > max_duration:
            overtime = duration - max_duration
            duration = max_duration

            self.logger.debug(f'ask_for({orig_duration}): requested duration ({orig_duration}) is greater than max ({max_duration}), overtime is {overtime}')

        self.duration += duration
        if self.is_started():
            til_end = self.stop_time - time.time()
            if til_end < 0:
                til_end = 0

            _prev_stop_time = self.stop_time
            _to_add = duration - til_end
            if _to_add < 0:
                _to_add = 0

            self.stop_time += _to_add
            self.logger.debug(f'ask_for({orig_duration}): adding {_to_add} to stop_time (before: {_prev_stop_time}, after: {self.stop_time})')

        return overtime

    def start(self, output: str):
        assert self.start_time == 0 and self.stop_time == 0, "already started?!"
        assert self.process is None, "self.process is not None, what the hell?"

        cur = time.time()
        self.start_time = cur
        self.stop_time = cur + self.duration

        cmd = self.get_command(output)
        self.logger.debug(f'start: running `{cmd}`')
        self.process = subprocess.Popen(cmd, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True)

        sh_pid = self.process.pid
        self.logger.debug(f'start: started, pid of shell is {sh_pid}')

        pid = self.find_recorder_program_pid(sh_pid)
        if pid is not None:
            self.recorder_program_pid = pid
            self.logger.debug(f'start: pid of {self.RECORDER_PROGRAM} is {pid}')

    def get_command(self, output: str) -> str:
        pass

    def stop(self):
        if self.process:
            if self.recorder_program_pid is None:
                self.recorder_program_pid = self.find_recorder_program_pid(self.process.pid)

            if self.recorder_program_pid is not None:
                os.kill(self.recorder_program_pid, signal.SIGINT)
                timeout = config['node']['process_wait_timeout']

                self.logger.debug(f'stop: sent SIGINT to {self.recorder_program_pid}. now waiting up to {timeout} seconds...')
                try:
                    self.process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    self.logger.warning(f'stop: wait({timeout}): timeout expired, killing it')
                    try:
                        os.kill(self.recorder_program_pid, signal.SIGKILL)
                        self.process.terminate()
                    except Exception as exc:
                        self.logger.exception(exc)
            else:
                self.logger.warning(f'stop: pid of {self.RECORDER_PROGRAM} is unknown, calling terminate()')
                self.process.terminate()

            rc = self.process.returncode
            self.logger.debug(f'stop: rc={rc}')

            self.process = None
            self.recorder_program_pid = 0

        self.duration = 0
        self.start_time = 0
        self.stop_time = 0

    def find_recorder_program_pid(self, sh_pid: int):
        try:
            children = find_child_processes(sh_pid)
        except OSError as exc:
            self.logger.warning(f'failed to find child process of {sh_pid}: ' + str(exc))
            return None

        for child in children:
            if self.RECORDER_PROGRAM in child.cmd:
                return child.pid

        return None

    @staticmethod
    def next_id() -> int:
        cur_id = Recording.g_record_id
        Recording.g_record_id += 1
        return cur_id

    def increment_id(self):
        self.record_id = Recording.next_id()


class Recorder:
    TEMP_NAME = None

    interrupted: bool
    lock: threading.Lock
    history_lock: threading.Lock
    recording: Optional[Recording]
    overtime: int
    history: RecordHistory
    next_history_cleanup_time: float
    storage: RecordStorage

    def __init__(self,
                 storage: RecordStorage,
                 recording: Recording):
        if self.TEMP_NAME is None:
            raise RuntimeError('this is abstract class')

        self.storage = storage
        self.recording = recording
        self.interrupted = False
        self.lock = threading.Lock()
        self.history_lock = threading.Lock()
        self.overtime = 0
        self.history = RecordHistory()
        self.next_history_cleanup_time = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    def start_thread(self):
        t = threading.Thread(target=self.loop)
        t.daemon = True
        t.start()

    def loop(self) -> None:
        tempname = os.path.join(self.storage.root, self.TEMP_NAME)

        while not self.interrupted:
            cur = time.time()
            stopped = False
            cur_record_id = None

            if self.next_history_cleanup_time == 0:
                self.next_history_cleanup_time = time.time() + _history_cleanup_freq
            elif self.next_history_cleanup_time <= time.time():
                self.logger.debug('loop: calling history.cleanup()')
                try:
                    self.history.cleanup()
                except Exception as e:
                    self.logger.error('loop: error while history.cleanup(): ' + str(e))
                self.next_history_cleanup_time = time.time() + _history_cleanup_freq

            with self.lock:
                cur_record_id = self.recording.record_id
                # self.logger.debug(f'cur_record_id={cur_record_id}')

                if not self.recording.is_started():
                    if self.recording.is_waiting():
                        try:
                            if os.path.exists(tempname):
                                self.logger.warning(f'loop: going to start new recording, but {tempname} still exists, unlinking..')
                                try:
                                    os.unlink(tempname)
                                except OSError as e:
                                    self.logger.exception(e)
                            self.recording.start(tempname)
                            with self.history_lock:
                                self.history[cur_record_id].mark_started(self.recording.start_time)
                        except Exception as exc:
                            self.logger.exception(exc)

                            # there should not be any errors, but still..
                            try:
                                self.recording.stop()
                            except Exception as exc:
                                self.logger.exception(exc)

                            with self.history_lock:
                                self.history[cur_record_id].mark_failed(exc)

                            self.logger.debug(f'loop: start exc path: calling increment_id()')
                            self.recording.increment_id()
                else:
                    if cur >= self.recording.stop_time:
                        try:
                            start_time = self.recording.start_time
                            stop_time = self.recording.stop_time
                            self.recording.stop()

                            saved_name = self.storage.save(tempname,
                                                           record_id=cur_record_id,
                                                           start_time=int(start_time),
                                                           stop_time=int(stop_time))

                            with self.history_lock:
                                self.history[cur_record_id].mark_finished(stop_time, saved_name)
                        except Exception as exc:
                            self.logger.exception(exc)
                            with self.history_lock:
                                self.history[cur_record_id].mark_failed(exc)
                        finally:
                            self.logger.debug(f'loop: stop exc final path: calling increment_id()')
                            self.recording.increment_id()

                        stopped = True

            if stopped and self.overtime > 0:
                self.logger.info(f'recording {cur_record_id} is stopped, but we\'ve got overtime ({self.overtime})')
                _overtime = self.overtime
                self.overtime = 0

                related_id = self.record(_overtime)
                self.logger.info(f'enqueued another record with id {related_id}')

                if cur_record_id is not None:
                    with self.history_lock:
                        self.history[cur_record_id].add_relation(related_id)

            time.sleep(0.2)

    def record(self, duration: int) -> int:
        self.logger.debug(f'record: duration={duration}')
        with self.lock:
            overtime = self.recording.ask_for(duration)
            self.logger.debug(f'overtime={overtime}')

            if overtime > self.overtime:
                self.overtime = overtime

            if not self.recording.is_started():
                with self.history_lock:
                    self.history.add(self.recording.record_id)

            return self.recording.record_id

    def stop(self):
        self.interrupted = True

    def get_info(self, record_id: int) -> RecordHistoryItem:
        with self.history_lock:
            return self.history[record_id]

    def forget(self, record_id: int):
        with self.history_lock:
            self.logger.info(f'forget: removing record {record_id} from history')
            self.history.delete(record_id)

    @staticmethod
    def get_max_record_time() -> int:
        return config['node']['record_max_time']


class SoundRecorder(Recorder):
    TEMP_NAME = 'temp.mp3'

    def __init__(self, *args, **kwargs):
        super().__init__(recording=SoundRecording(),
                         *args, **kwargs)


class CameraRecorder(Recorder):
    TEMP_NAME = 'temp.mp4'

    def __init__(self,
                 camera_type: CameraType,
                 *args, **kwargs):
        if camera_type == CameraType.ESP32:
            recording = ESP32CameraRecording(stream_addr=kwargs['stream_addr'])
            del kwargs['stream_addr']
        else:
            raise RuntimeError(f'unsupported camera type {camera_type}')

        super().__init__(recording=recording,
                         *args, **kwargs)


class SoundRecording(Recording):
    RECORDER_PROGRAM = 'arecord'

    def get_command(self, output: str) -> str:
        arecord = config['arecord']['bin']
        lame = config['lame']['bin']
        b = config['lame']['bitrate']

        return f'{arecord} -f S16 -r 44100 -t raw 2>/dev/null | {lame} -r -s 44.1 -b {b} -m m - {output} >/dev/null 2>/dev/null'


class ESP32CameraRecording(Recording):
    RECORDER_PROGRAM = 'esp32_capture.py'

    stream_addr: Addr

    def __init__(self, stream_addr: Addr):
        super().__init__()
        self.stream_addr = stream_addr

    def get_command(self, output: str) -> str:
        bin = config['esp32_capture']['bin']
        return f'{bin} --addr {self.stream_addr[0]}:{self.stream_addr[1]} --output-directory {output} >/dev/null 2>/dev/null'

    def start(self, output: str):
        output = os.path.dirname(output)
        return super().start(output)