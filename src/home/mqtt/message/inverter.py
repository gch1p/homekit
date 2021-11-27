import struct

from typing import Tuple


class Status:
    # 46 bytes
    format = 'IHHHHHHBHHHHHBHHHHHHHH'

    def pack(self, time: int, data: dict) -> bytes:
        bits = 0
        bits |= (data['mppt1_charger_status'] & 0x3)
        bits |= (data['mppt2_charger_status'] & 0x3) << 2
        bits |= (data['battery_power_direction'] & 0x3) << 4
        bits |= (data['dc_ac_power_direction'] & 0x3) << 6
        bits |= (data['line_power_direction'] & 0x3) << 8
        bits |= (data['load_connected'] & 0x1) << 10

        return struct.pack(
            self.format,
            time,
            int(data['grid_voltage'] * 10),
            int(data['grid_freq'] * 10),
            int(data['ac_output_voltage'] * 10),
            int(data['ac_output_freq'] * 10),
            data['ac_output_apparent_power'],
            data['ac_output_active_power'],
            data['output_load_percent'],
            int(data['battery_voltage'] * 10),
            int(data['battery_voltage_scc'] * 10),
            int(data['battery_voltage_scc2'] * 10),
            data['battery_discharging_current'],
            data['battery_charging_current'],
            data['battery_capacity'],
            data['inverter_heat_sink_temp'],
            data['mppt1_charger_temp'],
            data['mppt2_charger_temp'],
            data['pv1_input_power'],
            data['pv2_input_power'],
            int(data['pv1_input_voltage'] * 10),
            int(data['pv2_input_voltage'] * 10),
            bits
        )

    def unpack(self, buf: bytes) -> Tuple[int, dict]:
        data = struct.unpack(self.format, buf)
        return data[0], {
            'grid_voltage': data[1] / 10,
            'grid_freq': data[2] / 10,
            'ac_output_voltage': data[3] / 10,
            'ac_output_freq': data[4] / 10,
            'ac_output_apparent_power': data[5],
            'ac_output_active_power': data[6],
            'output_load_percent': data[7],
            'battery_voltage': data[8] / 10,
            'battery_voltage_scc': data[9] / 10,
            'battery_voltage_scc2': data[10] / 10,
            'battery_discharging_current': data[11],
            'battery_charging_current': data[12],
            'battery_capacity': data[13],
            'inverter_heat_sink_temp': data[14],
            'mppt1_charger_temp': data[15],
            'mppt2_charger_temp': data[16],
            'pv1_input_power': data[17],
            'pv2_input_power': data[18],
            'pv1_input_voltage': data[19] / 10,
            'pv2_input_voltage': data[20] / 10,
            'mppt1_charger_status': data[21] & 0x03,
            'mppt2_charger_status': (data[21] >> 2) & 0x03,
            'battery_power_direction': (data[21] >> 4) & 0x03,
            'dc_ac_power_direction': (data[21] >> 6) & 0x03,
            'line_power_direction': (data[21] >> 8) & 0x03,
            'load_connected': (data[21] >> 10) & 0x01,
        }


class Generation:
    # 8 bytes
    format = 'II'

    def pack(self, time: int, wh: int) -> bytes:
        return struct.pack(self.format, int(time), wh)

    def unpack(self, buf: bytes) -> tuple:
        data = struct.unpack(self.format, buf)
        return tuple(data)
