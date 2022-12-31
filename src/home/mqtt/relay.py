import paho.mqtt.client as mqtt
import re
import datetime

from .mqtt import MQTTBase
from typing import Optional, Union
from .payload.relay import (
    InitialStatPayload,
    StatPayload,
    PowerPayload,
    OTAPayload
)


class MQTTRelayDevice:
    id: str
    secret: Optional[str]

    def __init__(self, id: str, secret: Optional[str] = None):
        self.id = id
        self.secret = secret


class MQTTRelay(MQTTBase):
    _devices: list[MQTTRelayDevice]
    _message_callback: Optional[callable]
    _ota_publish_callback: Optional[callable]

    def __init__(self,
                 devices: Union[MQTTRelayDevice, list[MQTTRelayDevice]],
                 subscribe_to_updates=True):
        super().__init__(clean_session=True)
        if not isinstance(devices, list):
            devices = [devices]
        self._devices = devices
        self._message_callback = None
        self._ota_publish_callback = None
        self._subscribe_to_updates = subscribe_to_updates
        self._ota_mid = None

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)

        if self._subscribe_to_updates:
            for device in self._devices:
                topic = f'hk/{device.id}/relay/#'
                self._logger.info(f"subscribing to {topic}")
                client.subscribe(topic, qos=1)

    def on_publish(self, client: mqtt.Client, userdata, mid):
        if self._ota_mid is not None and mid == self._ota_mid and self._ota_publish_callback:
            self._ota_publish_callback()

    def set_message_callback(self, callback: callable):
        self._message_callback = callback

    def on_message(self, client: mqtt.Client, userdata, msg):
        try:
            match = re.match(r'^hk/(.*?)/relay/(stat|stat1|power|otares)$', msg.topic)
            self._logger.debug(f'topic: {msg.topic}')
            if not match:
                return

            device_id = match.group(1)
            subtopic = match.group(2)

            try:
                next(d for d in self._devices if d.id == device_id)
            except StopIteration:
                return

            message = None
            if subtopic == 'stat':
                message = StatPayload.unpack(msg.payload)
            elif subtopic == 'stat1':
                message = InitialStatPayload.unpack(msg.payload)
            elif subtopic == 'power':
                message = PowerPayload.unpack(msg.payload)

            if message and self._message_callback:
                self._message_callback(device_id, message)

        except Exception as e:
            self._logger.exception(str(e))

    def set_power(self, home_id, enable: bool):
        device = next(d for d in self._devices if d.id == home_id)
        assert device.secret is not None, 'device secret not specified'

        payload = PowerPayload(secret=device.secret,
                               state=enable)
        self._client.publish(f'hk/{device.id}/relay/power',
                             payload=payload.pack(),
                             qos=1)
        self._client.loop_write()

    def push_ota(self,
                 home_id,
                 filename: str,
                 publish_callback: callable,
                 qos: int):
        device = next(d for d in self._devices if d.id == home_id)
        assert device.secret is not None, 'device secret not specified'

        self._ota_publish_callback = publish_callback
        payload = OTAPayload(secret=device.secret, filename=filename)
        publish_result = self._client.publish(f'hk/{device.id}/relay/admin/ota',
                                              payload=payload.pack(),
                                              qos=qos)
        self._ota_mid = publish_result.mid
        self._client.loop_write()


class MQTTRelayState:
    enabled: bool
    update_time: datetime.datetime
    rssi: int
    fw_version: int
    ever_updated: bool

    def __init__(self):
        self.ever_updated = False
        self.enabled = False
        self.rssi = 0

    def update(self,
               enabled: bool,
               rssi: int,
               fw_version=None):
        self.ever_updated = True
        self.enabled = enabled
        self.rssi = rssi
        self.update_time = datetime.datetime.now()
        if fw_version:
            self.fw_version = fw_version
