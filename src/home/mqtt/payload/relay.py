from .base_payload import MQTTPayload, MQTTPayloadCustomField


class StatFlags(MQTTPayloadCustomField):
    state: bool
    config_changed_value_present: bool
    config_changed: bool

    @staticmethod
    def unpack(flags: int):
        state = flags & 0x1
        ccvp = (flags >> 1) & 0x1
        cc = (flags >> 2) & 0x1
        return StatFlags(state=(state == 1),
                         config_changed_value_present=(ccvp == 1),
                         config_changed=(cc == 1))

    def __index__(self):
        bits = 0
        bits |= (int(self.state) & 0x1)
        bits |= (int(self.config_changed_value_present) & 0x1) << 1
        bits |= (int(self.config_changed) & 0x1) << 2
        return bits


class InitialStatPayload(MQTTPayload):
    FORMAT = 'IBbIB'

    ip: int
    fw_version: int
    rssi: int
    free_heap: int
    flags: StatFlags


class StatPayload(MQTTPayload):
    FORMAT = 'bIB'

    rssi: int
    free_heap: int
    flags: StatFlags


class PowerPayload(MQTTPayload):
    FORMAT = '12sB'
    PACKER = {
        'state': lambda n: int(n)
    }
    UNPACKER = {
        'state': lambda n: bool(n)
    }

    secret: str
    state: bool
