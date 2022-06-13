#!/usr/bin/env python3
from home.api import WebAPIClient
from home.api.types import BotType
from home.config import config


if __name__ == '__main__':
    config.load('test_api')

    api = WebAPIClient()
    print(api.log_bot_request(BotType.ADMIN, 1, "test_api.py"))
