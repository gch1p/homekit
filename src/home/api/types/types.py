from enum import Enum, auto


class BotType(Enum):
    INVERTER = auto()
    PUMP = auto()
    SENSORS = auto()
    ADMIN = auto()
    SOUND = auto()


class TemperatureSensorLocation(Enum):
    BIG_HOUSE_1 = auto()
    BIG_HOUSE_2 = auto()
    STREET = auto()
    DIANA = auto()
    SPB1 = auto()


class TemperatureSensorDataType(Enum):
    TEMPERATURE = auto()
    RELATIVE_HUMIDITY = auto()


class SoundSensorLocation(Enum):
    DIANA = auto()
    BIG_HOUSE = auto()
    SPB1 = auto()

