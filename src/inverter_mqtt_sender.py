#!/usr/bin/env python3
import time
import datetime
import json
import inverterd

from home.config import config
from home.mqtt import MQTTBase, poll_tick
from home.mqtt.payload.inverter import Status, Generation


class MQTTClient(MQTTBase):
    def __init__(self):
        super().__init__()

        self._home_id = config['mqtt']['home_id']

        self._inverter = inverterd.Client()
        self._inverter.connect()
        self._inverter.format(inverterd.Format.SIMPLE_JSON)

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
                raw = self._inverter.exec('get-status')
            except inverterd.InverterError as e:
                self._logger.error(f'inverter error: {str(e)}')
                # TODO send to server
                continue

            data = json.loads(raw)['data']
            status = Status(time=round(now), **data)  # FIXME this will crash with 99% probability

            self._client.publish(f'hk/{self._home_id}/status',
                                 payload=status.pack(),
                                 qos=1)

            # read today's generation stat
            now = time.time()
            if gen_prev == 0 or now - gen_prev >= gen_freq:
                gen_prev = now
                today = datetime.date.today()
                try:
                    raw = self._inverter.exec('get-day-generated', (today.year, today.month, today.day))
                except inverterd.InverterError as e:
                    self._logger.error(f'inverter error: {str(e)}')
                    # TODO send to server
                    continue

                data = json.loads(raw)['data']
                gen = Generation(time=round(now), wh=data['wh'])
                self._client.publish(f'hk/{self._home_id}/gen',
                                     payload=gen.pack(),
                                     qos=1)


if __name__ == '__main__':
    config.load('inverter_mqtt_sender')

    client = MQTTClient()
    client.configure_tls()
    client.connect_and_loop(loop_forever=False)
    client.poll_inverter()