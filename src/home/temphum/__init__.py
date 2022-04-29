from .base import SensorType, TempHumSensor
from .si7021 import Si7021
from .dht12 import DHT12

__all__ = [
    'SensorType',
    'TempHumSensor',
    'create_sensor'
]


def create_sensor(type: SensorType, bus: int) -> TempHumSensor:
    if type == SensorType.Si7021:
        return Si7021(bus)
    elif type == SensorType.DHT12:
        return DHT12(bus)
    else:
        raise ValueError('unexpected sensor type')
