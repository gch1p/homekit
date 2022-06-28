#!/usr/bin/env python3
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..')
    )
])

import src.polaris as polaris


if __name__ == '__main__':
    sc = [cl for cl in polaris.protocol.CmdIncomingMessage.__subclasses__()
          if cl is not polaris.protocol.SimpleBooleanMessage]
    sc.extend(polaris.protocol.SimpleBooleanMessage.__subclasses__())
    for cl in sc:
        # if cl == polaris.protocol.HandshakeMessage:
        #     print('skip')
        #     continue
        print(cl.__name__, cl.TYPE)