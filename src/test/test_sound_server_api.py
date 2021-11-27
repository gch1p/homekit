#!/usr/bin/env python3
import sys
import os.path
sys.path.extend([
    os.path.realpath(
        os.path.join(os.path.dirname(os.path.join(__file__)), '..', '..')
    )
])
import threading

from time import sleep
from src.home.config import config
from src.home.api import WebAPIClient
from src.home.api.types import SoundSensorLocation

interrupted = False


class HitCounter:
    def __init__(self):
        self.sensors = {}
        self.lock = threading.Lock()
        self._reset_sensors()

    def _reset_sensors(self):
        for loc in SoundSensorLocation:
            self.sensors[loc.name.lower()] = 0

    def add(self, name: str, hits: int):
        if name not in self.sensors:
            raise ValueError(f'sensor {name} not found')

        with self.lock:
            self.sensors[name] += hits

    def get_all(self) -> list[tuple[str, int]]:
        vals = []
        with self.lock:
            for name, hits in self.sensors.items():
                if hits > 0:
                    vals.append((name, hits))
            self._reset_sensors()
        return vals


def hits_sender():
    while True:
        try:
            all_hits = hc.get_all()
            if all_hits:
                api.add_sound_sensor_hits(all_hits)
            sleep(5)
        except (KeyboardInterrupt, SystemExit):
            return


if __name__ == '__main__':
    config.load('test_api')

    hc = HitCounter()
    api = WebAPIClient()

    hc.add('spb1', 1)
    # hc.add('big_house', 123)

    hits_sender()
