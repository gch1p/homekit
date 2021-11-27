import time
import logging
import threading
import os.path

from tempfile import gettempdir
from .record import RecordStatus
from .node_client import SoundNodeClient
from ..util import Addr
from typing import Optional, Callable


class RecordClient:
    interrupted: bool
    logger: logging.Logger
    clients: dict[str, SoundNodeClient]
    awaiting: dict[str, dict[int, Optional[dict]]]
    error_handler: Optional[Callable]
    finished_handler: Optional[Callable]
    download_on_finish: bool

    def __init__(self,
                 nodes: dict[str, Addr],
                 error_handler: Optional[Callable] = None,
                 finished_handler: Optional[Callable] = None,
                 download_on_finish=False):
        self.interrupted = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self.clients = {}
        self.awaiting = {}
        self.download_on_finish = download_on_finish

        self.error_handler = error_handler
        self.finished_handler = finished_handler

        self.awaiting_lock = threading.Lock()

        for node, addr in nodes.items():
            self.clients[node] = SoundNodeClient(addr)
            self.awaiting[node] = {}

        try:
            t = threading.Thread(target=self.loop)
            t.daemon = True
            t.start()
        except (KeyboardInterrupt, SystemExit) as exc:
            self.stop()
            self.logger.exception(exc)

    def stop(self):
        self.interrupted = True

    def loop(self):
        while not self.interrupted:
            # self.logger.debug('loop: tick')

            for node in self.awaiting.keys():
                with self.awaiting_lock:
                    record_ids = list(self.awaiting[node].keys())
                if not record_ids:
                    continue

                self.logger.debug(f'loop: node `{node}` awaiting list: {record_ids}')

                cl = self.getclient(node)
                del_ids = []
                for rid in record_ids:
                    info = cl.record_info(rid)

                    if info['relations']:
                        for relid in info['relations']:
                            self.wait_for_record(node, relid, self.awaiting[node][rid], is_relative=True)

                    status = RecordStatus(info['status'])
                    if status in (RecordStatus.FINISHED, RecordStatus.ERROR):
                        if status == RecordStatus.FINISHED:
                            if self.download_on_finish:
                                local_fn = self.download(node, rid, info['file']['fileid'])
                            else:
                                local_fn = None
                            self._report_finished(info, local_fn, self.awaiting[node][rid])
                        else:
                            self._report_error(info, self.awaiting[node][rid])
                        del_ids.append(rid)
                        self.logger.debug(f'record {rid}: status {status}')

                if del_ids:
                    self.logger.debug(f'deleting {del_ids} from {node}\'s awaiting list')
                    with self.awaiting_lock:
                        for del_id in del_ids:
                            del self.awaiting[node][del_id]

            time.sleep(5)

        self.logger.info('loop ended')

    def getclient(self, node: str):
        return self.clients[node]

    def record(self,
               node: str,
               duration: int,
               userdata: Optional[dict] = None) -> int:
        self.logger.debug(f'record: node={node}, duration={duration}, userdata={userdata}')

        cl = self.getclient(node)
        record_id = cl.record(duration)['id']
        self.logger.debug(f'record: request sent, record_id={record_id}')

        self.wait_for_record(node, record_id, userdata)
        return record_id

    def wait_for_record(self,
                        node: str,
                        record_id: int,
                        userdata: Optional[dict] = None,
                        is_relative=False):
        with self.awaiting_lock:
            if record_id not in self.awaiting[node]:
                msg = f'wait_for_record: adding {record_id} to {node}'
                if is_relative:
                    msg += ' (by relation)'
                self.logger.debug(msg)

                self.awaiting[node][record_id] = userdata

    def download(self, node: str, record_id: int, fileid: str):
        dst = os.path.join(gettempdir(), f'{node}_{fileid}.mp3')
        cl = self.getclient(node)
        cl.record_download(record_id, dst)
        return dst

    def forget(self, node: str, rid: int):
        self.getclient(node).record_forget(rid)

    def _report_finished(self, *args):
        if self.finished_handler:
            self.finished_handler(*args)

    def _report_error(self, *args):
        if self.error_handler:
            self.error_handler(*args)
