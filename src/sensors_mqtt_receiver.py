#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import logging
import re

from home.mqtt import MQTTBase
from home.config import config
from home.mqtt.message import Temperature
from home.api.types import TemperatureSensorLocation
from home.database import SensorsDatabase

logger = logging.getLogger(__name__)


def get_sensor_type(sensor: str) -> TemperatureSensorLocation:
    for item in TemperatureSensorLocation:
        if sensor == item.name.lower():
            return item
    raise ValueError(f'unexpected sensor value: {sensor}')


class MQTTServer(MQTTBase):
    def __init__(self):
        super().__init__(clean_session=False)
        self.database = SensorsDatabase()

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)
        logger.info("subscribing to home/#")
        client.subscribe('home/#', qos=1)

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            variants = '|'.join([s.name.lower() for s in TemperatureSensorLocation])
            match = re.match(rf'home/(\d+)/si7021/({variants})', msg.topic)
            if not match:
                return

            home_id = int(match.group(1))
            sensor = get_sensor_type(match.group(2))

            packer = Temperature()
            client_time, temp, rh = packer.unpack(msg.payload)

            self.database.add_temperature(home_id, client_time, sensor,
                                          temp=int(temp*100),
                                          rh=int(rh*100))
        except Exception as e:
            logger.exception(str(e))


if __name__ == '__main__':
    config.load('sensors_mqtt_receiver')

    server = MQTTServer()
    server.connect_and_loop()
