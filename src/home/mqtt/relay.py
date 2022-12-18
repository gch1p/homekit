import paho.mqtt.client as mqtt
import re

from .mqtt import MQTTBase
from typing import Optional, Union
from .payload.relay import (
    InitialStatPayload,
    StatPayload,
    PowerPayload,
    OTAPayload
)


class MQTTRelay(MQTTBase):
    _home_id: Union[str, int]
    _secret: str
    _message_callback: Optional[callable]
    _ota_publish_callback: Optional[callable]

    def __init__(self,
                 home_id: Union[str, int],
                 secret: str,
                 subscribe_to_updates=True):
        super().__init__(clean_session=True)
        self._home_id = home_id
        self._secret = secret
        self._message_callback = None
        self._ota_publish_callback = None
        self._subscribe_to_updates = subscribe_to_updates
        self._ota_mid = None

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        super().on_connect(client, userdata, flags, rc)

        if self._subscribe_to_updates:
            topic = f'hk/{self._home_id}/relay/#'
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

            name = match.group(1)
            subtopic = match.group(2)

            if name != self._home_id:
                return

            message = None
            if subtopic == 'stat':
                message = StatPayload.unpack(msg.payload)
            elif subtopic == 'stat1':
                message = InitialStatPayload.unpack(msg.payload)
            elif subtopic == 'power':
                message = PowerPayload.unpack(msg.payload)

            if message and self._message_callback:
                self._message_callback(message)

        except Exception as e:
            self._logger.exception(str(e))

    def set_power(self, enable: bool):
        payload = PowerPayload(secret=self._secret,
                               state=enable)
        self._client.publish(f'hk/{self._home_id}/relay/power',
                             payload=payload.pack(),
                             qos=1)
        self._client.loop_write()

    def push_ota(self,
                 filename: str,
                 publish_callback: callable,
                 qos: int):
        self._ota_publish_callback = publish_callback
        payload = OTAPayload(secret=self._secret, filename=filename)
        publish_result = self._client.publish(f'hk/{self._home_id}/relay/admin/ota',
                                              payload=payload.pack(),
                                              qos=qos)
        self._ota_mid = publish_result.mid
        self._client.loop_write()
