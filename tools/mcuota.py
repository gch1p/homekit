#!/usr/bin/env python3
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..')
    )
])

from time import sleep
from argparse import ArgumentParser
from src.home.config import config
from src.home.mqtt import MQTTRelay, MQTTRelayDevice


def guess_filename(product: str, build_target: str):
    return os.path.join(
        products_dir,
        product,
        '.pio',
        'build',
        build_target,
        'firmware.bin'
    )


def relayctl_publish_ota(filename: str,
                         home_id: str,
                         home_secret: str,
                         qos: int):
    global stop

    def published():
        global stop
        stop = True

    mqtt_relay = MQTTRelay(devices=MQTTRelayDevice(id=home_id, secret=home_secret))
    mqtt_relay.configure_tls()
    mqtt_relay.connect_and_loop(loop_forever=False)
    mqtt_relay.push_ota(home_id, filename, published, qos)
    while not stop:
        sleep(0.1)
    mqtt_relay.disconnect()


stop = False
products = {
    'relayctl': {
        'build_target': 'esp12e',
        'callback': relayctl_publish_ota
    }
}

products_dir = os.path.join(
    os.path.dirname(__file__),
    '..',
    'platformio'
)


def main():
    parser = ArgumentParser()
    parser.add_argument('--filename', type=str)
    parser.add_argument('--home-id', type=str, required=True)
    parser.add_argument('--product', type=str, required=True)
    parser.add_argument('--qos', type=int, default=1)

    config.load('mcuota_push', parser=parser)
    arg = parser.parse_args()

    if arg.product not in products:
        raise ValueError(f'invalid product: \'{arg.product}\' not found')

    if arg.home_id not in config['mqtt']['home_secrets']:
        raise ValueError(f'home_secret for home {arg.home_id} not found in config!')

    filename = arg.filename if arg.filename else guess_filename(arg.product, products[arg.product]['build_target'])
    if not os.path.exists(filename):
        raise OSError(f'file \'{filename}\' does not exists')

    print('Please confirm following OTA params.')
    print('')
    print(f'      Home ID: {arg.home_id}')
    print(f'      Product: {arg.product}')
    print(f'Firmware file: {filename}')
    print('')
    input('Press any key to continue or Ctrl+C to abort.')

    products[arg.product]['callback'](filename, arg.home_id, config['mqtt']['home_secrets'][arg.home_id], qos=arg.qos)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
