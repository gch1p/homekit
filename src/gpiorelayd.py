#!/usr/bin/env python3
import logging
import os
import sys

from home.config import config
from home.relay.sunxi_h3_server import RelayServer

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    if not os.getegid() == 0:
        sys.exit('Must be run as root.')

    config.load()

    try:
        s = RelayServer(pinname=config.get('relayd.pin'),
                        addr=config.get_addr('relayd.listen'))
        s.run()
    except KeyboardInterrupt:
        logger.info('Exiting...')
