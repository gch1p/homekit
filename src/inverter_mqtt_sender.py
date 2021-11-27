#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import logging
import time
import datetime
import json
import inverterd

from home.config import config
from home.mqtt import MQTTBase, poll_tick
from home.mqtt.message import Status, Generation

logger = logging.getLogger(__name__)


class MQTTClient(MQTTBase):
    def __init__(self):
        super().__init__()

        self.inverter = inverterd.Client()
        self.inverter.connect()
        self.inverter.format(inverterd.Format.SIMPLE_JSON)

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)

    def poll_inverter(self):
        freq = int(config['mqtt']['inverter']['poll_freq'])
        gen_freq = int(config['mqtt']['inverter']['generation_poll_freq'])

        g = poll_tick(freq)
        gen_prev = 0
        while True:
            time.sleep(next(g))

            # read status
            now = time.time()
            try:
                raw = self.inverter.exec('get-status')
            except inverterd.InverterError as e:
                logger.error(f'inverter error: {str(e)}')
                # TODO send to server
                continue

            data = json.loads(raw)['data']

            packer = Status()
            self.client.publish(f'home/{self.home_id}/status',
                                payload=packer.pack(round(now), data),
                                qos=1)

            # read today's generation stat
            now = time.time()
            if gen_prev == 0 or now - gen_prev >= gen_freq:
                gen_prev = now
                today = datetime.date.today()
                try:
                    raw = self.inverter.exec('get-day-generated', (today.year, today.month, today.day))
                except inverterd.InverterError as e:
                    logger.error(f'inverter error: {str(e)}')
                    # TODO send to server
                    continue

                # print('raw:', raw, type(raw))
                data = json.loads(raw)['data']
                packer = Generation()
                self.client.publish(f'home/{self.home_id}/gen',
                                    payload=packer.pack(round(now), data['wh']),
                                    qos=1)


if __name__ == '__main__':
    config.load('inverter_mqtt_sender')

    client = MQTTClient()
    client.configure_tls()
    client.connect_and_loop(loop_forever=False)
    client.poll_inverter()