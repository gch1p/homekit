#!/usr/bin/env python3
import sys, os.path
sys.path.extend([
    os.path.realpath(os.path.join(os.path.dirname(os.path.join(__file__)), '..', '..')),
])

from src.home.api.errors import ApiResponseError
from src.home.sound import SoundNodeClient


if __name__ == '__main__':
    client = SoundNodeClient(('127.0.0.1', 8313))
    print(client.amixer_get_all())

    try:
        client.amixer_get('invalidname')
    except ApiResponseError as exc:
        print(exc)

