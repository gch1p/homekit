#!/usr/bin/env python3
import logging
import os
import sys

from home.config import config
from home.util import parse_addr
from home.soundsensor import SoundSensorNode

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    if not os.getegid() == 0:
        sys.exit('Must be run as root.')

    config.load('sound_sensor_node')

    kwargs = {}
    if 'delay' in config['node']:
        kwargs['delay'] = config['node']['delay']

    if 'server_addr' in config['node']:
        server_addr = parse_addr(config['node']['server_addr'])
    else:
        server_addr = None

    node = SoundSensorNode(name=config['node']['name'],
                           pinname=config['node']['pin'],
                           threshold=config['node']['threshold'] if 'threshold' in config['node'] else 1,
                           server_addr=server_addr,
                           **kwargs)
    node.run()
