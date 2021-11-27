#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import logging
import time
import json

from home.util import parse_addr, MySimpleSocketClient
from home.mqtt import MQTTBase, poll_tick
from home.mqtt.message import Temperature
from home.config import config

logger = logging.getLogger(__name__)


class MQTTClient(MQTTBase):
    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)

    def poll(self):
        freq = int(config['mqtt']['sensors']['poll_freq'])
        logger.debug(f'freq={freq}')

        g = poll_tick(freq)
        while True:
            time.sleep(next(g))
            for k, v in config['mqtt']['sensors']['si7021'].items():
                host, port = parse_addr(v['addr'])
                self.publish_si7021(host, port, k)

    def publish_si7021(self, host: str, port: int, name: str):
        logging.debug(f"publish_si7021/{name}: {host}:{port}")

        try:
            now = time.time()
            socket = MySimpleSocketClient(host, port)

            socket.write('read')
            response = json.loads(socket.read().strip())

            temp = response['temp']
            humidity = response['humidity']

            logging.debug(f'publish_si7021/{name}: temp={temp} humidity={humidity}')

            packer = Temperature()
            self.client.publish(f'home/{self.home_id}/si7021/{name}',
                                payload=packer.pack(round(now), temp, humidity),
                                qos=1)
        except Exception as e:
            logger.exception(e)


if __name__ == '__main__':
    config.load('sensors_mqtt_sender')

    client = MQTTClient()
    client.configure_tls()
    client.connect_and_loop(loop_forever=False)
    client.poll()
