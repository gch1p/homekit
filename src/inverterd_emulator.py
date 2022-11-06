#!/usr/bin/env python3
import logging

from home.inverter.emulator import InverterEmulator


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    InverterEmulator(addr=('127.0.0.1', 8305))
