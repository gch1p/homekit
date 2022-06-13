#!/usr/bin/env python3
import logging
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..', '..')
    )
])

import time

from src.home.api import WebAPIClient, RequestParams
from src.home.config import config
from src.home.media import SoundRecordClient
from src.home.util import parse_addr

logger = logging.getLogger(__name__)


# record callbacks
# ----------------

def record_error(info: dict, userdata: dict):
    node = userdata['node']
    # TODO


def record_finished(info: dict, fn: str, userdata: dict):
    logger.info('record finished: ' + str(info))

    node = userdata['node']
    api.upload_recording(fn, node, info['id'], int(info['start_time']), int(info['stop_time']))


# api client callbacks
# --------------------

def api_error_handler(exc, name, req: RequestParams):
    if name == 'upload_recording':
        logger.error('failed to upload recording, exception below')
        logger.exception(exc)

    else:
        logger.error(f'api call ({name}, params={req.params}) failed, exception below')
        logger.exception(exc)


def api_success_handler(response, name, req: RequestParams):
    if name == 'upload_recording':
        node = req.params['node']
        rid = req.params['record_id']

        logger.debug(f'successfully uploaded recording (node={node}, record_id={rid}), api response:' + str(response))

        # deleting temp file
        try:
            os.unlink(req.files['file'])
        except OSError as exc:
            logger.error(f'error while deleting temp file:')
            logger.exception(exc)

        record.forget(node, rid)


if __name__ == '__main__':
    config.load('test_record_upload')

    nodes = {}
    for name, addr in config['nodes'].items():
        nodes[name] = parse_addr(addr)
    record = SoundRecordClient(nodes,
                               error_handler=record_error,
                               finished_handler=record_finished,
                               download_on_finish=True)

    api = WebAPIClient()
    api.enable_async(error_handler=api_error_handler,
                     success_handler=api_success_handler)

    record_id = record.record('localhost', 3, {'node': 'localhost'})
    print(f'record_id: {record_id}')

    while True:
        try:
            time.sleep(0.1)
        except (KeyboardInterrupt, SystemExit):
            break