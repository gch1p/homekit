from enum import Enum, auto


class BatteryPowerDirection(Enum):
    DISCHARGING = auto()
    CHARGING = auto()
    DO_NOTHING = auto()


class ChargingEvent(Enum):
    AC_CHARGING_UNAVAILABLE_BECAUSE_SOLAR = auto()
    AC_NOT_CHARGING = auto()
    AC_CHARGING_STARTED = auto()
    AC_DISCONNECTED = auto()
    AC_CURRENT_CHANGED = auto()
    AC_MOSTLY_CHARGED = auto()
    AC_CHARGING_FINISHED = auto()

    UTIL_CHARGING_STARTED = auto()
    UTIL_CHARGING_STOPPED = auto()
    UTIL_CHARGING_STOPPED_SOLAR = auto()


class ACPresentEvent(Enum):
    CONNECTED = auto()
    DISCONNECTED = auto()


class ChargingState(Enum):
    NOT_CHARGING = auto()
    AC_BUT_SOLAR = auto()
    AC_WAITING = auto()
    AC_OK = auto()
    AC_DONE = auto()


class CurrentChangeDirection(Enum):
    UP = auto()
    DOWN = auto()


class BatteryState(Enum):
    NORMAL = auto()
    LOW = auto()
    CRITICAL = auto()


class ACMode(Enum):
    GENERATOR = 'generator'
    UTILITIES = 'utilities'


class OutputSourcePriority(Enum):
    SolarUtilityBattery = 'SUB'
    SolarBatteryUtility = 'SBU'

    @classmethod
    def from_text(cls, s: str):
        if s == 'Solar-Battery-Utility':
            return cls.SolarBatteryUtility
        elif s == 'Solar-Utility-Battery':
            return cls.SolarUtilityBattery
        else:
            raise ValueError(f'unknown value: {s}')