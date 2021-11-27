#!/usr/bin/env python3
import logging
import threading
import os

from time import sleep
from typing import Optional
from home.config import config
from home.util import parse_addr
from home.api import WebAPIClient, RequestParams
from home.api.types import SoundSensorLocation
from home.soundsensor import SoundSensorServer, SoundSensorHitHandler
from home.sound import RecordClient

interrupted = False
logger = logging.getLogger(__name__)
server: SoundSensorServer


def get_related_sound_nodes(sensor_name: str) -> list[str]:
    if sensor_name not in config['sensor_to_sound_nodes_relations']:
        raise ValueError(f'unexpected sensor name {sensor_name}')
    return config['sensor_to_sound_nodes_relations'][sensor_name]


def get_sound_node_config(name: str) -> Optional[dict]:
    if name in config['sound_nodes']:
        return config['sound_nodes'][name]
    else:
        return None


class HitCounter:
    def __init__(self):
        self.sensors = {}
        self.lock = threading.Lock()
        self._reset_sensors()

    def _reset_sensors(self):
        for loc in SoundSensorLocation:
            self.sensors[loc.name.lower()] = 0

    def add(self, name: str, hits: int):
        if name not in self.sensors:
            raise ValueError(f'sensor {name} not found')

        with self.lock:
            self.sensors[name] += hits

    def get_all(self) -> list[tuple[str, int]]:
        vals = []
        with self.lock:
            for name, hits in self.sensors.items():
                if hits > 0:
                    vals.append((name, hits))
            self._reset_sensors()
        return vals


class HitHandler(SoundSensorHitHandler):
    def handler(self, name: str, hits: int):
        if not hasattr(SoundSensorLocation, name.upper()):
            logger.error(f'invalid sensor name: {name}')
            return

        node_config = get_sound_node_config(name)
        if node_config is None:
            logger.error(f'config for node {name} not found')
            return

        min_hits = node_config['min_hits'] if 'min_hits' in node_config else 1
        if hits < min_hits:
            return

        hc.add(name, hits)

        if server.is_recording_enabled():
            try:
                nodes = get_related_sound_nodes(name)
                for node in nodes:
                    durations = config['sound_nodes'][node]['durations']
                    dur = durations[1] if hits > min_hits else durations[0]
                    record.record(node, dur*60, {'node': node})
            except ValueError as exc:
                logger.exception(exc)


def hits_sender():
    while not interrupted:
        all_hits = hc.get_all()
        if all_hits:
            api.add_sound_sensor_hits(all_hits)
        sleep(5)


api: Optional[WebAPIClient] = None
hc: Optional[HitCounter] = None
record: Optional[RecordClient] = None


# record callbacks

# ----------------

def record_error(info: dict, userdata: dict):
    node = userdata['node']
    logger.error('recording ' + str(dict) + ' from node ' + node + ' failed')

    record.forget(node, info['id'])


def record_finished(info: dict, fn: str, userdata: dict):
    logger.debug('record finished: ' + str(info))

    # audio could have been requested by other user (telegram bot, for example)
    # so we shouldn't 'forget' it here

    # node = userdata['node']
    # record.forget(node, info['id'])


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
    config.load('sound_sensor_server')

    hc = HitCounter()
    api = WebAPIClient(timeout=(10, 60))
    api.enable_async(error_handler=api_error_handler,
                     success_handler=api_success_handler)

    t = threading.Thread(target=hits_sender)
    t.daemon = True
    t.start()

    nodes = {}
    for nodename, nodecfg in config['sound_nodes'].items():
        nodes[nodename] = parse_addr(nodecfg['addr'])

    record = RecordClient(nodes,
                          error_handler=record_error,
                          finished_handler=record_finished)

    try:
        server = SoundSensorServer(parse_addr(config['server']['listen']), HitHandler)
        server.run()
    except KeyboardInterrupt:
        interrupted = True
        record.stop()
        logging.info('keyboard interrupt, exiting...')
