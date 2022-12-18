from .base_payload import MQTTPayload

_mult_100 = lambda n: int(n*100)
_div_100 = lambda n: n/100


class Temperature(MQTTPayload):
    FORMAT = 'IhH'
    PACKER = {
        'temp': _mult_100,
        'rh': _mult_100,
    }
    UNPACKER = {
        'temp': _div_100,
        'rh': _div_100,
    }

    time: int
    temp: float
    rh: float
