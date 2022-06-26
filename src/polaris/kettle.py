# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import logging
import zeroconf

import cryptography.hazmat.primitives._serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives import hashes

from functools import partial
from abc import ABC
from ipaddress import ip_address
from typing import Optional

from .protocol import (
    Connection,
    ModeMessage,
    HandshakeMessage,
    TargetTemperatureMessage,
    Message,
    PowerType
)

_logger = logging.getLogger(__name__)


# Polaris PWK 1725CGLD IoT kettle
class Kettle(zeroconf.ServiceListener, ABC):
    macaddr: str
    device_token: str
    sb: Optional[zeroconf.ServiceBrowser]
    found_device: Optional[zeroconf.ServiceInfo]
    conn: Optional[Connection]

    def __init__(self, mac: str, device_token: str):
        super().__init__()
        self.zeroconf = zeroconf.Zeroconf()
        self.sb = None
        self.macaddr = mac
        self.device_token = device_token
        self.found_device = None
        self.conn = None

    def find(self) -> zeroconf.ServiceInfo:
        self.sb = zeroconf.ServiceBrowser(self.zeroconf, "_syncleo._udp.local.", self)
        self.sb.join()

        return self.found_device

    # zeroconf.ServiceListener implementation
    def add_service(self,
                    zc: zeroconf.Zeroconf,
                    type_: str,
                    name: str) -> None:
        if name.startswith(f'{self.macaddr}.'):
            info = zc.get_service_info(type_, name)
            try:
                self.sb.cancel()
            except RuntimeError:
                pass
            self.zeroconf.close()
            self.found_device = info

            assert self.device_curve == 29, f'curve type {self.device_curve} is not implemented'

    def start_server(self, callback: callable):
        addresses = list(map(ip_address, self.found_device.addresses))
        self.conn = Connection(addr=addresses[0],
                               port=int(self.found_device.port),
                               device_pubkey=self.device_pubkey,
                               device_token=bytes.fromhex(self.device_token))

        # shake the kettle's hand
        self._pass_message(HandshakeMessage(), callback)
        self.conn.start()

    def stop_server(self):
        self.conn.interrupted = True

    @property
    def device_pubkey(self) -> bytes:
        return bytes.fromhex(self.found_device.properties[b'public'].decode())

    @property
    def device_curve(self) -> int:
        return int(self.found_device.properties[b'curve'].decode())

    def set_power(self, power_type: PowerType, callback: callable):
        self._pass_message(ModeMessage(power_type), callback)

    def set_target_temperature(self, temp: int, callback: callable):
        self._pass_message(TargetTemperatureMessage(temp), callback)

    def _pass_message(self, message: Message, callback: callable):
        self.conn.send_message(message, partial(callback, self))
