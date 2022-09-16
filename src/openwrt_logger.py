#!/usr/bin/env python3
import os

from datetime import datetime
from home.config import config
from home.database import SimpleState
from home.api import WebAPIClient
from typing import Tuple, List

log_file = '/var/log/openwrt.log'

f"""
This script is supposed to be run by cron every 5 minutes or so.
It looks for new lines in {log_file} and sends them to remote server.

OpenWRT must have remote logging enabled (UDP; IP of host this script is launched on; port 514)

/etc/rsyslog.conf contains following (assuming 192.168.1.1 is the router IP):

$ModLoad imudp  
$UDPServerRun 514  
:fromhost-ip, isequal, "192.168.1.1" /var/log/openwrt.log  
& ~

Also comment out the following line: 
$ActionFileDefaultTemplate RSYSLOG_TraditionalFileFormat
 
"""


def parse_line(line: str) -> Tuple[int, str]:
    space_pos = line.index(' ')

    date = line[:space_pos]
    rest = line[space_pos+1:]

    return (
        int(datetime.strptime(date, "%Y-%m-%dT%H:%M:%S%z").timestamp()),
        rest
    )


if __name__ == '__main__':
    config.load('openwrt_logger')

    state = SimpleState(file=config['simple_state']['file'],
                        default={'seek': 0, 'size': 0})

    fsize = os.path.getsize(log_file)
    if fsize < state['size']:
        state['seek'] = 0

    with open(log_file, 'r') as f:
        if state['seek']:
            # jump to the latest read position
            f.seek(state['seek'])

        # read till the end of the file
        content = f.read()

        # save new position
        state['seek'] = f.tell()
        state['size'] = fsize

        lines: List[Tuple[int, str]] = []

        if content != '':
            for line in content.strip().split('\n'):
                if not line:
                    continue

                try:
                    lines.append(parse_line(line))
                except ValueError:
                    lines.append((0, line))

            api = WebAPIClient()
            api.log_openwrt(lines)
