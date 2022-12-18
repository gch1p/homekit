#!/usr/bin/env python3
import time
import json

from home.util import parse_addr, MySimpleSocketClient
from home.mqtt import MQTTBase, poll_tick
from home.mqtt.payload.sensors import Temperature
from home.config import config


class MQTTClient(MQTTBase):
    def __init__(self):
        super().__init__(self)
        self._home_id = config['mqtt']['home_id']

    def poll(self):
        freq = int(config['mqtt']['sensors']['poll_freq'])
        self._logger.debug(f'freq={freq}')

        g = poll_tick(freq)
        while True:
            time.sleep(next(g))
            for k, v in config['mqtt']['sensors']['si7021'].items():
                host, port = parse_addr(v['addr'])
                self.publish_si7021(host, port, k)

    def publish_si7021(self, host: str, port: int, name: str):
        self._logger.debug(f"publish_si7021/{name}: {host}:{port}")

        try:
            now = time.time()
            socket = MySimpleSocketClient(host, port)

            socket.write('read')
            response = json.loads(socket.read().strip())

            temp = response['temp']
            humidity = response['humidity']

            self._logger.debug(f'publish_si7021/{name}: temp={temp} humidity={humidity}')

            pld = Temperature(time=round(now),
                              temp=temp,
                              rh=humidity)
            self._client.publish(f'hk/{self._home_id}/si7021/{name}',
                                 payload=pld.pack(),
                                 qos=1)
        except Exception as e:
            self._logger.exception(e)


if __name__ == '__main__':
    config.load('sensors_mqtt_sender')

    client = MQTTClient()
    client.configure_tls()
    client.connect_and_loop(loop_forever=False)
    client.poll()
