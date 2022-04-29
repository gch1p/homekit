from .base import I2CTempHumSensor


class Si7021(I2CTempHumSensor):
    i2c_addr = 0x40

    def temperature(self) -> float:
        raw = self.bus.read_i2c_block_data(self.i2c_addr, 0xE3, 2)
        return 175.72 * (raw[0] << 8 | raw[1]) / 65536.0 - 46.85

    def humidity(self) -> float:
        raw = self.bus.read_i2c_block_data(self.i2c_addr, 0xE5, 2)
        return 125.0 * (raw[0] << 8 | raw[1]) / 65536.0 - 6.0
