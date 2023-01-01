#!/usr/bin/env python3
from typing import Optional
from argparse import ArgumentParser

from home.config import config
from home.mqtt import MQTTRelay, MQTTRelayDevice
from home.mqtt.payload import MQTTPayload
from home.mqtt.payload.relay import (
    InitialStatPayload, StatPayload, OTAResultPayload
)

mqtt_relay: Optional[MQTTRelay] = None


def on_mqtt_message(device_id, p: MQTTPayload):
    message = None

    if isinstance(p, InitialStatPayload) or isinstance(p, StatPayload):
        message = f'[stat] state={"on" if p.flags.state else "off"}'
        message += f' rssi={p.rssi}'
        message += f' free_heap={p.free_heap}'
        if isinstance(p, InitialStatPayload):
            message += f' fw={p.fw_version}'

    elif isinstance(p, OTAResultPayload):
        message = f'[otares] result={p.result} error_code={p.error_code}'

    if message:
        print(message)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--device-id', type=str, required=True)

    config.load('relay_mqtt_util', parser=parser)
    arg = parser.parse_args()

    mqtt_relay = MQTTRelay(devices=MQTTRelayDevice(id=arg.device_id))
    mqtt_relay.set_message_callback(on_mqtt_message)
    mqtt_relay.configure_tls()
    try:
        mqtt_relay.connect_and_loop()
    except KeyboardInterrupt:
        mqtt_relay.disconnect()
