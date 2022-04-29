import smbus

from abc import abstractmethod, ABC
from enum import Enum


class TempHumSensor:
    @abstractmethod
    def humidity(self) -> float:
        pass

    @abstractmethod
    def temperature(self) -> float:
        pass


class I2CTempHumSensor(TempHumSensor, ABC):
    def __init__(self, bus: int):
        super().__init__()
        self.bus = smbus.SMBus(bus)


class SensorType(Enum):
    Si7021 = 'si7021'
    DHT12 = 'dht12'
