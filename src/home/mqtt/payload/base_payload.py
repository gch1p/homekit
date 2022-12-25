import abc
import struct
import re

from typing import Optional, Tuple


class MQTTPayload(abc.ABC):
    FORMAT = ''
    PACKER = {}
    UNPACKER = {}

    def __init__(self, **kwargs):
        for field in self.__class__.__annotations__:
            setattr(self, field, kwargs[field])

    def pack(self):
        args = []
        bf_number = -1
        bf_arg = 0
        bf_progress = 0

        for field, field_type in self.__class__.__annotations__.items():
            bfp = _bit_field_params(field_type)
            if bfp:
                n, s, b = bfp
                if n != bf_number:
                    if bf_number != -1:
                        args.append(bf_arg)
                    bf_number = n
                    bf_progress = 0
                    bf_arg = 0
                bf_arg |= (getattr(self, field) & (2 ** b - 1)) << bf_progress
                bf_progress += b

            else:
                if bf_number != -1:
                    args.append(bf_arg)
                    bf_number = -1
                    bf_progress = 0
                    bf_arg = 0

                args.append(self._pack_field(field))

        if bf_number != -1:
            args.append(bf_arg)

        return struct.pack(self.FORMAT, *args)

    @classmethod
    def unpack(cls, buf: bytes):
        data = struct.unpack(cls.FORMAT, buf)
        kwargs = {}
        i = 0
        bf_number = -1
        bf_progress = 0

        for field, field_type in cls.__annotations__.items():
            bfp = _bit_field_params(field_type)
            if bfp:
                n, s, b = bfp
                if n != bf_number:
                    bf_number = n
                    bf_progress = 0
                kwargs[field] = (data[i] >> bf_progress) & (2 ** b - 1)
                bf_progress += b
                continue  # don't increment i

            if bf_number != -1:
                bf_number = -1
                i += 1

            if issubclass(field_type, MQTTPayloadCustomField):
                kwargs[field] = field_type.unpack(data[i])
            else:
                kwargs[field] = cls._unpack_field(field, data[i])
            i += 1

        return cls(**kwargs)

    def _pack_field(self, name):
        val = getattr(self, name)
        if self.PACKER and name in self.PACKER:
            return self.PACKER[name](val)
        else:
            return val

    @classmethod
    def _unpack_field(cls, name, val):
        if isinstance(val, MQTTPayloadCustomField):
            return
        if cls.UNPACKER and name in cls.UNPACKER:
            return cls.UNPACKER[name](val)
        else:
            return val


class MQTTPayloadCustomField(abc.ABC):
    def __init__(self, **kwargs):
        for field in self.__class__.__annotations__:
            setattr(self, field, kwargs[field])

    @abc.abstractmethod
    def __index__(self):
        pass

    @classmethod
    @abc.abstractmethod
    def unpack(cls, *args, **kwargs):
        pass


def bit_field(seq_no: int, total_bits: int, bits: int):
    return type(f'MQTTPayloadBitField_{seq_no}_{total_bits}_{bits}', (object,), {
        'seq_no': seq_no,
        'total_bits': total_bits,
        'bits': bits
    })


def _bit_field_params(cl) -> Optional[Tuple[int, ...]]:
    match = re.match(r'MQTTPayloadBitField_(\d+)_(\d+)_(\d)$', cl.__name__)
    if match is not None:
        return tuple([int(match.group(i)) for i in range(1, 4)])
    return None
