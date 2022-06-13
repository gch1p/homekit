from enum import Enum, auto


class MediaNodeType(Enum):
    SOUND = auto()
    CAMERA = auto()


class RecordStatus(Enum):
    WAITING = auto()
    RECORDING = auto()
    FINISHED = auto()
    ERROR = auto()
