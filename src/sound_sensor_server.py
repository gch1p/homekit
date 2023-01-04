#!/usr/bin/env python3
import logging
import threading

from time import sleep
from typing import Optional, List, Dict, Tuple
from functools import partial
from home.config import config
from home.util import parse_addr
from home.api import WebAPIClient, RequestParams
from home.api.types import SoundSensorLocation
from home.soundsensor import SoundSensorServer, SoundSensorHitHandler
from home.media import MediaNodeType, SoundRecordClient, CameraRecordClient, RecordClient

interrupted = False
logger = logging.getLogger(__name__)
server: SoundSensorServer


def get_related_nodes(node_type: MediaNodeType,
                      sensor_name: str) -> List[str]:
    try:
        if sensor_name not in config[f'sensor_to_{node_type.name.lower()}_nodes_relations']:
            raise ValueError(f'unexpected sensor name {sensor_name}')
        return config[f'sensor_to_{node_type.name.lower()}_nodes_relations'][sensor_name]
    except KeyError:
        return []


def get_node_config(node_type: MediaNodeType,
                    name: str) -> Optional[dict]:
    if name in config[f'{node_type.name.lower()}_nodes']:
        cfg = config[f'{node_type.name.lower()}_nodes'][name]
        if 'min_hits' not in cfg:
            cfg['min_hits'] = 1
        return cfg
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

    def get_all(self) -> List[Tuple[str, int]]:
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

        should_continue = False
        for node_type in MediaNodeType:
            try:
                nodes = get_related_nodes(node_type, name)
            except ValueError:
                logger.error(f'config for {node_type.name.lower()} node {name} not found')
                return

            for node in nodes:
                node_config = get_node_config(node_type, node)
                if node_config is None:
                    logger.error(f'config for {node_type.name.lower()} node {node} not found')
                    continue
                if hits < node_config['min_hits']:
                    continue
                should_continue = True

        if not should_continue:
            return

        hc.add(name, hits)

        if not server.is_recording_enabled():
            return
        for node_type in MediaNodeType:
            try:
                nodes = get_related_nodes(node_type, name)
                for node in nodes:
                    node_config = get_node_config(node_type, node)
                    if node_config is None:
                        logger.error(f'node config for {node_type.name.lower()} node {node} not found')
                        continue

                    durations = node_config['durations']
                    dur = durations[1] if hits > node_config['min_hits'] else durations[0]
                    record_clients[node_type].record(node, dur*60, {'node': node})

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
record_clients: Dict[MediaNodeType, RecordClient] = {}


# record callbacks
# ----------------

def record_error(type: MediaNodeType,
                 info: dict,
                 userdata: dict):
    node = userdata['node']
    logger.error('recording ' + str(dict) + f' from {type.name.lower()} node ' + node + ' failed')

    record_clients[type].forget(node, info['id'])


def record_finished(type: MediaNodeType,
                    info: dict,
                    fn: str,
                    userdata: dict):
    logger.debug(f'{type.name.lower()} record finished: ' + str(info))

    # audio could have been requested by other user (telegram bot, for example)
    # so we shouldn't 'forget' it here

    # node = userdata['node']
    # record.forget(node, info['id'])


# api client callbacks
# --------------------

def api_error_handler(exc, name, req: RequestParams):
    logger.error(f'api call ({name}, params={req.params}) failed, exception below')
    logger.exception(exc)


if __name__ == '__main__':
    config.load('sound_sensor_server')

    hc = HitCounter()
    api = WebAPIClient(timeout=(10, 60))
    api.enable_async(error_handler=api_error_handler)

    t = threading.Thread(target=hits_sender)
    t.daemon = True
    t.start()

    sound_nodes = {}
    if 'sound_nodes' in config:
        for nodename, nodecfg in config['sound_nodes'].items():
            sound_nodes[nodename] = parse_addr(nodecfg['addr'])

    camera_nodes = {}
    if 'camera_nodes' in config:
        for nodename, nodecfg in config['camera_nodes'].items():
            camera_nodes[nodename] = parse_addr(nodecfg['addr'])

    if sound_nodes:
        record_clients[MediaNodeType.SOUND] = SoundRecordClient(sound_nodes,
                                                                error_handler=partial(record_error, MediaNodeType.SOUND),
                                                                finished_handler=partial(record_finished, MediaNodeType.SOUND))

    if camera_nodes:
        record_clients[MediaNodeType.CAMERA] = CameraRecordClient(camera_nodes,
                                                                  error_handler=partial(record_error, MediaNodeType.CAMERA),
                                                                  finished_handler=partial(record_finished, MediaNodeType.CAMERA))

    try:
        server = SoundSensorServer(config.get_addr('server.listen'), HitHandler)
        server.run()
    except KeyboardInterrupt:
        interrupted = True
        for c in record_clients.values():
            c.stop()
        logging.info('keyboard interrupt, exiting...')
