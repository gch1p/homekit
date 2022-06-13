#!/usr/bin/env python3
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..')
    )
])

from argparse import ArgumentParser
from src.home.util import send_datagram, stringify, parse_addr


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--name', type=str, required=True,
                        help='node name, like `diana`')
    parser.add_argument('--hits', type=int, required=True,
                        help='hits count')
    parser.add_argument('--server', type=str, required=True,
                        help='center server addr in host:port format')

    args = parser.parse_args()

    send_datagram(stringify([args.name, args.hits]), parse_addr(args.server))
