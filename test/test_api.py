#!/usr/bin/env python3
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..')
    )
])

from src.home.api import WebAPIClient
from src.home.api.types import BotType
from src.home.config import config


if __name__ == '__main__':
    config.load('test_api')

    api = WebAPIClient()
    print(api.log_bot_request(BotType.ADMIN, 1, "test_api.py"))
