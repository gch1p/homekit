#!/usr/bin/env python3
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..', '..')
    )
])

from pprint import pprint
from argparse import ArgumentParser
from time import sleep
from src.home.util import parse_addr
from src.home.camera import esp32
from src.home.config import config

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--addr', type=str, required=True,
                        help='camera server address, in host:port format')
    parser.add_argument('--status', action='store_true',
                        help='print status and exit')

    arg = config.load(False, parser=parser)
    cam = esp32.WebClient(addr=parse_addr(arg.addr))

    if arg.status:
        status = cam.getstatus()
        pprint(status)
        sys.exit(0)

    if cam.syncsettings(dict(
        vflip=True,
        hmirror=True,
        framesize=esp32.FrameSize.SVGA_800x600,
        lenc=True,
        wpc=False,
        bpc=False,
        raw_gma=False,
        agc=True,
        gainceiling=5,
        quality=10,
        awb_gain=False,
        awb=True,
        aec_dsp=True,
        aec=True
    )) is True:
        print('some settings were changed, sleeping for 0.5 sec')
        sleep(0.5)

    # cam.setdelay(200)

    cam.setflash(True)
    sleep(0.2)
    cam.capture('/tmp/capture.jpg')
    cam.setflash(False)
