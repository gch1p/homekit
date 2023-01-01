import hashlib

from .base_payload import MQTTPayload, MQTTPayloadCustomField


# _logger = logging.getLogger(__name__)

class StatFlags(MQTTPayloadCustomField):
    state: bool
    config_changed_value_present: bool
    config_changed: bool

    @staticmethod
    def unpack(flags: int):
        # _logger.debug(f'StatFlags.unpack: flags={flags}')
        state = flags & 0x1
        ccvp = (flags >> 1) & 0x1
        cc = (flags >> 2) & 0x1
        # _logger.debug(f'StatFlags.unpack: state={state}')
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
    FORMAT = '=IBbIB'

    ip: int
    fw_version: int
    rssi: int
    free_heap: int
    flags: StatFlags


class StatPayload(MQTTPayload):
    FORMAT = '=bIB'

    rssi: int
    free_heap: int
    flags: StatFlags


class PowerPayload(MQTTPayload):
    FORMAT = '=12sB'
    PACKER = {
        'state': lambda n: int(n),
        'secret': lambda s: s.encode('utf-8')
    }
    UNPACKER = {
        'state': lambda n: bool(n),
        'secret': lambda s: s.decode('utf-8')
    }

    secret: str
    state: bool


class OTAResultPayload(MQTTPayload):
    FORMAT = '=BB'
    result: int
    error_code: int


class OTAPayload(MQTTPayload):
    secret: str
    filename: str

    # structure of returned data:
    #
    # uint8_t[len(secret)] secret;
    # uint8_t[16] md5;
    # *uint8_t data

    def pack(self):
        buf = bytearray(self.secret.encode())
        m = hashlib.md5()
        with open(self.filename, 'rb') as fd:
            content = fd.read()
            m.update(content)
            buf.extend(m.digest())
            buf.extend(content)
        return buf

    def unpack(cls, buf: bytes):
        raise RuntimeError(f'{cls.__class__.__name__}.unpack: not implemented')
        # secret = buf[:12].decode()
        # filename = buf[12:].decode()
        # return OTAPayload(secret=secret, filename=filename)

