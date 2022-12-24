#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause

import logging
import sys
import paho.mqtt.client as mqtt

from typing import Optional
from argparse import ArgumentParser
from queue import SimpleQueue
from home.mqtt import MQTTBase
from home.config import config
from syncleo import (
    Kettle,
    PowerType,
    protocol as kettle_proto
)

k: Optional[Kettle] = None
logger = logging.getLogger(__name__)
control_tasks = SimpleQueue()


class MQTTServer(MQTTBase):
    def __init__(self):
        super().__init__(clean_session=False)

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        logger.info("subscribing to #")
        client.subscribe('#', qos=1)

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            print(msg.topic, msg.payload)

        except Exception as e:
            logger.exception(str(e))


def kettle_connection_established(response: kettle_proto.MessageResponse):
    try:
        assert isinstance(response, kettle_proto.AckMessage), f'ACK expected, but received: {response}'
    except AssertionError:
        k.stop_all()
        return

    def next_task(response: kettle_proto.MessageResponse):
        try:
            assert response is not False, 'server error'
        except AssertionError:
            k.stop_all()
            return

        if not control_tasks.empty():
            task = control_tasks.get()
            f, args = task(k)
            args.append(next_task)
            f(*args)
        else:
            k.stop_all()

    next_task(response)


def main():
    tempmin = 30
    tempmax = 100
    tempstep = 5

    parser = ArgumentParser()
    parser.add_argument('-m', dest='mode', required=True, type=str, choices=('mqtt', 'control'))
    parser.add_argument('--on', action='store_true')
    parser.add_argument('--off', action='store_true')
    parser.add_argument('-t', '--temperature', dest='temp', type=int, default=tempmax,
                        choices=range(tempmin, tempmax+tempstep, tempstep))

    arg = config.load('polaris_kettle_util', use_cli=True, parser=parser)

    if arg.mode == 'mqtt':
        server = MQTTServer()
        try:
            server.connect_and_loop(loop_forever=True)
        except KeyboardInterrupt:
            pass

    elif arg.mode == 'control':
        if arg.on and arg.off:
            raise RuntimeError('--on and --off are mutually exclusive')

        if arg.off:
            control_tasks.put(lambda k: (k.set_power, [PowerType.OFF]))
        else:
            if arg.temp == tempmax:
                control_tasks.put(lambda k: (k.set_power, [PowerType.ON]))
            else:
                control_tasks.put(lambda k: (k.set_target_temperature, [arg.temp]))
                control_tasks.put(lambda k: (k.set_power, [PowerType.CUSTOM]))

        k = Kettle(mac=config['kettle']['mac'], device_token=config['kettle']['token'])
        info = k.discover()
        if not info:
            print('no device found.')
            return 1

        print('found service:', info)
        k.start_server_if_needed(kettle_connection_established)

    return 0


if __name__ == '__main__':
    sys.exit(main())
