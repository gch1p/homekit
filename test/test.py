#!/usr/bin/env python
from home.relay import RelayClient


if __name__ == '__main__':
    c = RelayClient()
    print(c, c._host)