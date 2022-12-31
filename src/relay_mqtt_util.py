#!/usr/bin/env python3
from typing import Optional
from argparse import ArgumentParser

from home.config import config
from home.mqtt import MQTTRelay, MQTTRelayDevice
from home.mqtt.payload import MQTTPayload
from home.mqtt.payload.relay import InitialStatPayload, StatPayload

mqtt_relay: Optional[MQTTRelay] = None


def on_mqtt_message(device_id, message: MQTTPayload):
    if isinstance(message, InitialStatPayload) or isinstance(message, StatPayload):
        message = f'[{device_id}] state={message.flags.state} rssi={message.rssi}'
        if isinstance(message, InitialStatPayload):
            message += f' fw={message.fw_version}'
        print(message)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--device-id', type=str, required=True)

    config.load('relay_mqtt_util', parser=parser)
    arg = parser.parse_args()

    mqtt_relay = MQTTRelay(devices=MQTTRelayDevice(id=arg.device_id))
    mqtt_relay.set_message_callback(on_mqtt_message)
    mqtt_relay.configure_tls()
    mqtt_relay.connect_and_loop()
