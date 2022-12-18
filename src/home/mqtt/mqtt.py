import os.path
import paho.mqtt.client as mqtt
import ssl
import logging

from typing import Tuple
from ..config import config


def username_and_password() -> Tuple[str, str]:
    username = config['mqtt']['username'] if 'username' in config['mqtt'] else None
    password = config['mqtt']['password'] if 'password' in config['mqtt'] else None
    return username, password


class MQTTBase:
    def __init__(self, clean_session=True):
        self._client = mqtt.Client(client_id=config['mqtt']['client_id'],
                                   protocol=mqtt.MQTTv311,
                                   clean_session=clean_session)
        self._client.on_connect = self.on_connect
        self._client.on_disconnect = self.on_disconnect
        self._client.on_message = self.on_message
        self._client.on_log = self.on_log
        self._client.on_publish = self.on_publish
        self._loop_started = False

        self._logger = logging.getLogger(self.__class__.__name__)

        username, password = username_and_password()
        if username and password:
            self._logger.debug(f'username={username} password={password}')
            self._client.username_pw_set(username, password)

    def configure_tls(self):
        ca_certs = os.path.realpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '..',
            '..',
            '..',
            'assets',
            'mqtt_ca.crt'
        ))
        self._client.tls_set(ca_certs=ca_certs, cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2)

    def connect_and_loop(self, loop_forever=True):
        host = config['mqtt']['host']
        port = config['mqtt']['port']

        self._client.connect(host, port, 60)
        if loop_forever:
            self._client.loop_forever()
        else:
            self._client.loop_start()
            self._loop_started = True

    def disconnect(self):
        self._client.disconnect()
        self._client.loop_write()
        self._client.loop_stop()

    def on_connect(self, client: mqtt.Client, userdata, flags, rc):
        self._logger.info("Connected with result code " + str(rc))

    def on_disconnect(self, client: mqtt.Client, userdata, rc):
        self._logger.info("Disconnected with result code " + str(rc))

    def on_log(self, client: mqtt.Client, userdata, level, buf):
        level = mqtt.LOGGING_LEVEL[level] if level in mqtt.LOGGING_LEVEL else logging.INFO
        self._logger.log(level, f'MQTT: {buf}')

    def on_message(self, client: mqtt.Client, userdata, msg):
        self._logger.debug(msg.topic + ": " + str(msg.payload))

    def on_publish(self, client: mqtt.Client, userdata, mid):
        self._logger.debug(f'publish done, mid={mid}')