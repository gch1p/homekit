from .base import I2CTempHumSensor


class DHT12(I2CTempHumSensor):
    i2c_addr = 0x5C
        
    def _measure(self):
        raw = self.bus.read_i2c_block_data(self.i2c_addr, 0, 5)
        if (raw[0] + raw[1] + raw[2] + raw[3]) & 0xff != raw[4]:
            raise ValueError("checksum error")
        return raw

    def temperature(self) -> float:
        raw = self._measure()
        temp = raw[2] + (raw[3] & 0x7f) * 0.1
        if raw[3] & 0x80:
            temp *= -1
        return temp

    def humidity(self) -> float:
        raw = self._measure()
        return raw[0] + raw[1] * 0.1
