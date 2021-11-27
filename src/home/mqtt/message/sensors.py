import struct

from typing import Tuple


class Temperature:
    format = 'IhH'

    def pack(self, time: int, temp: float, rh: float) -> bytes:
        return struct.pack(
            self.format,
            time,
            int(temp*100),
            int(rh*100)
        )

    def unpack(self, buf: bytes) -> Tuple[int, float, float]:
        data = struct.unpack(self.format, buf)
        return data[0], data[1]/100, data[2]/100
