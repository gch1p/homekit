import struct

from .base_payload import MQTTPayload, MQTTPayloadBitField
from typing import Tuple

_mult_10 = lambda n: int(n*10)
_div_10 = lambda n: n/10


class Status(MQTTPayload):
    # 46 bytes
    FORMAT = 'IHHHHHHBHHHHHBHHHHHHHH'

    PACKER = {
        'grid_voltage': _mult_10,
        'grid_freq': _mult_10,
        'ac_output_voltage': _mult_10,
        'ac_output_freq': _mult_10,
        'battery_voltage': _mult_10,
        'battery_voltage_scc': _mult_10,
        'battery_voltage_scc2': _mult_10,
        'pv1_input_voltage': _mult_10,
        'pv2_input_voltage': _mult_10
    }
    UNPACKER = {
        'grid_voltage': _div_10,
        'grid_freq': _div_10,
        'ac_output_voltage': _div_10,
        'ac_output_freq': _div_10,
        'battery_voltage': _div_10,
        'battery_voltage_scc': _div_10,
        'battery_voltage_scc2': _div_10,
        'pv1_input_voltage': _div_10,
        'pv2_input_voltage': _div_10
    }

    time: int
    grid_voltage: float
    grid_freq: float
    ac_output_voltage: float
    ac_output_freq: float
    ac_output_apparent_power: int
    ac_output_active_power: int
    output_load_percent: int
    battery_voltage: float
    battery_voltage_scc: float
    battery_voltage_scc2: float
    battery_discharge_current: int
    battery_charge_current: int
    battery_capacity: int
    inverter_heat_sink_temp: int
    mppt1_charger_temp: int
    mppt2_charger_temp: int
    pv1_input_power: int
    pv2_input_power: int
    pv1_input_voltage: float
    pv2_input_voltage: float

    # H
    mppt1_charger_status: MQTTPayloadBitField[0, 16, 2]
    mppt2_charger_status: MQTTPayloadBitField[0, 16, 2]
    battery_power_direction: MQTTPayloadBitField[0, 16, 2]
    dc_ac_power_direction: MQTTPayloadBitField[0, 16, 2]
    line_power_direction: MQTTPayloadBitField[0, 16, 2]
    load_connected: MQTTPayloadBitField[0, 16, 1]


class Generation(MQTTPayload):
    # 8 bytes
    FORMAT = 'II'

    time: int
    wh: int
