#!/usr/bin/env python3
from home import http
from home.config import config
from home.mqtt import MQTTRelay, MQTTRelayDevice, MQTTRelayState
from home.mqtt.payload import MQTTPayload
from home.mqtt.payload.relay import InitialStatPayload, StatPayload
from typing import Optional

mqtt_relay: Optional[MQTTRelay] = None
relay_states: dict[str, MQTTRelayState] = {}


def on_mqtt_message(device_id, message: MQTTPayload):
    if isinstance(message, InitialStatPayload) or isinstance(message, StatPayload):
        kwargs = dict(rssi=message.rssi, enabled=message.flags.state)
        if device_id not in relay_states:
            relay_states[device_id] = MQTTRelayState()
        relay_states[device_id].update(**kwargs)


class RelayMqttHttpProxy(http.HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get('/relay/{id}/on', self.relay_on)
        self.get('/relay/{id}/off', self.relay_off)
        self.get('/relay/{id}/toggle', self.relay_toggle)

    async def _relay_on_off(self,
                            enable: Optional[bool],
                            req: http.Request):
        device_id = req.match_info['id']
        device_secret = req.query['secret']

        if enable is None:
            if device_id in relay_states and relay_states[device_id].ever_updated:
                cur_state = relay_states[device_id].enabled
            else:
                cur_state = False
            enable = not cur_state

        mqtt_relay.set_power(device_id, enable, device_secret)
        return self.ok()

    async def relay_on(self, req: http.Request):
        return await self._relay_on_off(True, req)

    async def relay_off(self, req: http.Request):
        return await self._relay_on_off(False, req)

    async def relay_toggle(self, req: http.Request):
        return await self._relay_on_off(None, req)


if __name__ == '__main__':
    config.load('relay_mqtt_http_proxy')

    mqtt_relay = MQTTRelay(devices=[MQTTRelayDevice(id=device_id) for device_id in config.get('relay.devices')])
    mqtt_relay.configure_tls()
    mqtt_relay.set_message_callback(on_mqtt_message)
    mqtt_relay.connect_and_loop(loop_forever=False)

    proxy = RelayMqttHttpProxy(config.get_addr('server.listen'))
    try:
        proxy.run()
    except KeyboardInterrupt:
        mqtt_relay.disconnect()
