import asyncio
import logging

from inverterd import Format

from typing import Union
from enum import Enum
from ..util import Addr, stringify


class InverterEnum(Enum):
    def as_text(self) -> str:
        raise RuntimeError('abstract method')


class BatteryType(InverterEnum):
    AGM = 0
    Flooded = 1
    User = 2

    def as_text(self) -> str:
        return ('AGM', 'Flooded', 'User')[self.value]


class InputVoltageRange(InverterEnum):
    Appliance = 0
    USP = 1

    def as_text(self) -> str:
        return ('Appliance', 'USP')[self.value]


class OutputSourcePriority(InverterEnum):
    SolarUtilityBattery = 0
    SolarBatteryUtility = 1

    def as_text(self) -> str:
        return ('Solar-Utility-Battery', 'Solar-Battery-Utility')[self.value]


class ChargeSourcePriority(InverterEnum):
    SolarFirst = 0
    SolarAndUtility = 1
    SolarOnly = 2

    def as_text(self) -> str:
        return ('Solar-First', 'Solar-and-Utility', 'Solar-only')[self.value]


class MachineType(InverterEnum):
    OffGridTie = 0
    GridTie = 1

    def as_text(self) -> str:
        return ('Off-Grid-Tie', 'Grid-Tie')[self.value]


class Topology(InverterEnum):
    TransformerLess = 0
    Transformer = 1

    def as_text(self) -> str:
        return ('Transformer-less', 'Transformer')[self.value]


class OutputMode(InverterEnum):
    SingleOutput = 0
    ParallelOutput = 1
    Phase_1_of_3 = 2
    Phase_2_of_3 = 3
    Phase_3_of_3 = 4

    def as_text(self) -> str:
        return (
            'Single output',
            'Parallel output',
            'Phase 1 of 3-phase output',
            'Phase 2 of 3-phase output',
            'Phase 3 of 3-phase'
        )[self.value]


class SolarPowerPriority(InverterEnum):
    BatteryLoadUtility = 0
    LoadBatteryUtility = 1

    def as_text(self) -> str:
        return ('Battery-Load-Utility', 'Load-Battery-Utility')[self.value]


class MPPTChargerStatus(InverterEnum):
    Abnormal = 0
    NotCharging = 1
    Charging = 2

    def as_text(self) -> str:
        return ('Abnormal', 'Not charging', 'Charging')[self.value]


class BatteryPowerDirection(InverterEnum):
    DoNothing = 0
    Charge = 1
    Discharge = 2

    def as_text(self) -> str:
        return ('Do nothing', 'Charge', 'Discharge')[self.value]


class DC_AC_PowerDirection(InverterEnum):
    DoNothing = 0
    AC_DC = 1
    DC_AC = 2

    def as_text(self) -> str:
        return ('Do nothing', 'AC/DC', 'DC/AC')[self.value]


class LinePowerDirection(InverterEnum):
    DoNothing = 0
    Input = 1
    Output = 2

    def as_text(self) -> str:
        return ('Do nothing', 'Input', 'Output')[self.value]


class WorkingMode(InverterEnum):
    PowerOnMode = 0
    StandbyMode = 1
    BypassMode = 2
    BatteryMode = 3
    FaultMode = 4
    HybridMode = 5

    def as_text(self) -> str:
        return (
            'Power on mode',
            'Standby mode',
            'Bypass mode',
            'Battery mode',
            'Fault mode',
            'Hybrid mode'
        )[self.value]


class ParallelConnectionStatus(InverterEnum):
    NotExistent = 0
    Existent = 1

    def as_text(self) -> str:
        return ('Non-existent', 'Existent')[self.value]


class LoadConnectionStatus(InverterEnum):
    Disconnected = 0
    Connected = 1

    def as_text(self) -> str:
        return ('Disconnected', 'Connected')[self.value]


class ConfigurationStatus(InverterEnum):
    Default = 0
    Changed = 1

    def as_text(self) -> str:
        return ('Default', 'Changed')[self.value]


_g_human_readable = {"grid_voltage": "Grid voltage",
                     "grid_freq": "Grid frequency",
                     "ac_output_voltage": "AC output voltage",
                     "ac_output_freq": "AC output frequency",
                     "ac_output_apparent_power": "AC output apparent power",
                     "ac_output_active_power": "AC output active power",
                     "output_load_percent": "Output load percent",
                     "battery_voltage": "Battery voltage",
                     "battery_voltage_scc": "Battery voltage from SCC",
                     "battery_voltage_scc2": "Battery voltage from SCC2",
                     "battery_discharge_current": "Battery discharge current",
                     "battery_charge_current": "Battery charge current",
                     "battery_capacity": "Battery capacity",
                     "inverter_heat_sink_temp": "Inverter heat sink temperature",
                     "mppt1_charger_temp": "MPPT1 charger temperature",
                     "mppt2_charger_temp": "MPPT2 charger temperature",
                     "pv1_input_power": "PV1 input power",
                     "pv2_input_power": "PV2 input power",
                     "pv1_input_voltage": "PV1 input voltage",
                     "pv2_input_voltage": "PV2 input voltage",
                     "configuration_status": "Configuration state",
                     "mppt1_charger_status": "MPPT1 charger status",
                     "mppt2_charger_status": "MPPT2 charger status",
                     "load_connected": "Load connection",
                     "battery_power_direction": "Battery power direction",
                     "dc_ac_power_direction": "DC/AC power direction",
                     "line_power_direction": "Line power direction",
                     "local_parallel_id": "Local parallel ID",
                     "ac_input_rating_voltage": "AC input rating voltage",
                     "ac_input_rating_current": "AC input rating current",
                     "ac_output_rating_voltage": "AC output rating voltage",
                     "ac_output_rating_freq": "AC output rating frequency",
                     "ac_output_rating_current": "AC output rating current",
                     "ac_output_rating_apparent_power": "AC output rating apparent power",
                     "ac_output_rating_active_power": "AC output rating active power",
                     "battery_rating_voltage": "Battery rating voltage",
                     "battery_recharge_voltage": "Battery re-charge voltage",
                     "battery_redischarge_voltage": "Battery re-discharge voltage",
                     "battery_under_voltage": "Battery under voltage",
                     "battery_bulk_voltage": "Battery bulk voltage",
                     "battery_float_voltage": "Battery float voltage",
                     "battery_type": "Battery type",
                     "max_charge_current": "Max charge current",
                     "max_ac_charge_current": "Max AC charge current",
                     "input_voltage_range": "Input voltage range",
                     "output_source_priority": "Output source priority",
                     "charge_source_priority": "Charge source priority",
                     "parallel_max_num": "Parallel max num",
                     "machine_type": "Machine type",
                     "topology": "Topology",
                     "output_mode": "Output mode",
                     "solar_power_priority": "Solar power priority",
                     "mppt": "MPPT string",
                     "fault_code": "Fault code",
                     "line_fail": "Line fail",
                     "output_circuit_short": "Output circuit short",
                     "inverter_over_temperature": "Inverter over temperature",
                     "fan_lock": "Fan lock",
                     "battery_voltage_high": "Battery voltage high",
                     "battery_low": "Battery low",
                     "battery_under": "Battery under",
                     "over_load": "Over load",
                     "eeprom_fail": "EEPROM fail",
                     "power_limit": "Power limit",
                     "pv1_voltage_high": "PV1 voltage high",
                     "pv2_voltage_high": "PV2 voltage high",
                     "mppt1_overload_warning": "MPPT1 overload warning",
                     "mppt2_overload_warning": "MPPT2 overload warning",
                     "battery_too_low_to_charge_for_scc1": "Battery too low to charge for SCC1",
                     "battery_too_low_to_charge_for_scc2": "Battery too low to charge for SCC2",
                     "buzzer": "Buzzer",
                     "overload_bypass": "Overload bypass function",
                     "escape_to_default_screen_after_1min_timeout": "Escape to default screen after 1min timeout",
                     "overload_restart": "Overload restart",
                     "over_temp_restart": "Over temperature restart",
                     "backlight_on": "Backlight on",
                     "alarm_on_on_primary_source_interrupt": "Alarm on on primary source interrupt",
                     "fault_code_record": "Fault code record",
                     "wh": "Wh"}


class InverterEmulator:
    def __init__(self, addr: Addr, wait=True):
        self.status = {"grid_voltage": {"unit": "V", "value": 236.3},
                       "grid_freq": {"unit": "Hz", "value": 50.0},
                       "ac_output_voltage": {"unit": "V", "value": 229.9},
                       "ac_output_freq": {"unit": "Hz", "value": 50.0},
                       "ac_output_apparent_power": {"unit": "VA", "value": 207},
                       "ac_output_active_power": {"unit": "Wh", "value": 146},
                       "output_load_percent": {"unit": "%", "value": 4},
                       "battery_voltage": {"unit": "V", "value": 49.1},
                       "battery_voltage_scc": {"unit": "V", "value": 0.0},
                       "battery_voltage_scc2": {"unit": "V", "value": 0.0},
                       "battery_discharge_current": {"unit": "A", "value": 3},
                       "battery_charge_current": {"unit": "A", "value": 0},
                       "battery_capacity": {"unit": "%", "value": 69},
                       "inverter_heat_sink_temp": {"unit": "°C", "value": 17},
                       "mppt1_charger_temp": {"unit": "°C", "value": 0},
                       "mppt2_charger_temp": {"unit": "°C", "value": 0},
                       "pv1_input_power": {"unit": "Wh", "value": 0},
                       "pv2_input_power": {"unit": "Wh", "value": 0},
                       "pv1_input_voltage": {"unit": "V", "value": 0.0},
                       "pv2_input_voltage": {"unit": "V", "value": 0.0},
                       "configuration_status": ConfigurationStatus.Default,
                       "mppt1_charger_status": MPPTChargerStatus.Abnormal,
                       "mppt2_charger_status": MPPTChargerStatus.Abnormal,
                       "load_connected": LoadConnectionStatus.Connected,
                       "battery_power_direction": BatteryPowerDirection.Discharge,
                       "dc_ac_power_direction": DC_AC_PowerDirection.DC_AC,
                       "line_power_direction": LinePowerDirection.DoNothing,
                       "local_parallel_id": 0}

        self.rated = {"ac_input_rating_voltage": {"unit": "V", "value": 230.0},
                      "ac_input_rating_current": {"unit": "A", "value": 21.7},
                      "ac_output_rating_voltage": {"unit": "V", "value": 230.0},
                      "ac_output_rating_freq": {"unit": "Hz", "value": 50.0},
                      "ac_output_rating_current": {"unit": "A", "value": 21.7},
                      "ac_output_rating_apparent_power": {"unit": "VA", "value": 5000},
                      "ac_output_rating_active_power": {"unit": "Wh", "value": 5000},
                      "battery_rating_voltage": {"unit": "V", "value": 48.0},
                      "battery_recharge_voltage": {"unit": "V", "value": 48.0},
                      "battery_redischarge_voltage": {"unit": "V", "value": 55.0},
                      "battery_under_voltage": {"unit": "V", "value": 42.0},
                      "battery_bulk_voltage": {"unit": "V", "value": 57.6},
                      "battery_float_voltage": {"unit": "V", "value": 54.0},
                      "battery_type": BatteryType.User,
                      "max_charge_current": {"unit": "A", "value": 60},
                      "max_ac_charge_current": {"unit": "A", "value": 30},
                      "input_voltage_range": InputVoltageRange.Appliance,
                      "output_source_priority": OutputSourcePriority.SolarBatteryUtility,
                      "charge_source_priority": ChargeSourcePriority.SolarAndUtility,
                      "parallel_max_num": 6,
                      "machine_type": MachineType.OffGridTie,
                      "topology": Topology.TransformerLess,
                      "output_mode": OutputMode.SingleOutput,
                      "solar_power_priority": SolarPowerPriority.LoadBatteryUtility,
                      "mppt": "2"}

        self.errors = {"fault_code": 0,
                       "line_fail": False,
                       "output_circuit_short": False,
                       "inverter_over_temperature": False,
                       "fan_lock": False,
                       "battery_voltage_high": False,
                       "battery_low": False,
                       "battery_under": False,
                       "over_load": False,
                       "eeprom_fail": False,
                       "power_limit": False,
                       "pv1_voltage_high": False,
                       "pv2_voltage_high": False,
                       "mppt1_overload_warning": False,
                       "mppt2_overload_warning": False,
                       "battery_too_low_to_charge_for_scc1": False,
                       "battery_too_low_to_charge_for_scc2": False}

        self.flags = {"buzzer": False,
                      "overload_bypass": True,
                      "escape_to_default_screen_after_1min_timeout": False,
                      "overload_restart": True,
                      "over_temp_restart": True,
                      "backlight_on": False,
                      "alarm_on_on_primary_source_interrupt": True,
                      "fault_code_record": False}

        self.day_generated = 1000

        self.logger = logging.getLogger(self.__class__.__name__)

        host, port = addr
        asyncio.run(self.run_server(host, port, wait))
        # self.max_ac_charge_current = 30
        # self.max_charge_current = 60
        # self.charge_thresholds = [48, 54]

    async def run_server(self, host, port, wait: bool):
        server = await asyncio.start_server(self.client_handler, host, port)
        async with server:
            self.logger.info(f'listening on {host}:{port}')
            if wait:
                await server.serve_forever()
            else:
                asyncio.ensure_future(server.serve_forever())

    async def client_handler(self, reader, writer):
        client_fmt = Format.JSON

        def w(s: str):
            writer.write(s.encode('utf-8'))

        def return_error(message=None):
            w('err\r\n')
            if message:
                if client_fmt in (Format.JSON, Format.SIMPLE_JSON):
                    w(stringify({
                        'result': 'error',
                        'message': message
                    }))
                elif client_fmt in (Format.TABLE, Format.SIMPLE_TABLE):
                    w(f'error: {message}')
                w('\r\n')
            w('\r\n')

        def return_ok(data=None):
            w('ok\r\n')
            if client_fmt in (Format.JSON, Format.SIMPLE_JSON):
                jdata = {
                    'result': 'ok'
                }
                if data:
                    jdata['data'] = data
                w(stringify(jdata))
                w('\r\n')
            elif data:
                w(data)
                w('\r\n')
            w('\r\n')

        request = None
        while request != 'quit':
            try:
                request = await reader.read(255)
                if request == b'\x04':
                    break
                request = request.decode('utf-8').strip()
            except Exception:
                break

            if request.startswith('format '):
                requested_format = request[7:]
                try:
                    client_fmt = Format(requested_format)
                except ValueError:
                    return_error('invalid format')

                return_ok()

            elif request.startswith('exec '):
                buf = request[5:].split(' ')
                command = buf[0]
                args = buf[1:]

                try:
                    return_ok(self.process_command(client_fmt, command, *args))
                except ValueError as e:
                    return_error(str(e))

            else:
                return_error(f'invalid token: {request}')

            try:
                await writer.drain()
            except ConnectionResetError as e:
                # self.logger.exception(e)
                pass

        writer.close()

    def process_command(self, fmt: Format, c: str, *args) -> Union[dict, str, list[int], None]:
        ac_charge_currents = [2, 10, 20, 30, 40, 50, 60]

        if c == 'get-status':
            return self.format_dict(self.status, fmt)

        elif c == 'get-rated':
            return self.format_dict(self.rated, fmt)

        elif c == 'get-errors':
            return self.format_dict(self.errors, fmt)

        elif c == 'get-flags':
            return self.format_dict(self.flags, fmt)

        elif c == 'get-day-generated':
            return self.format_dict({'wh': 1000}, fmt)

        elif c == 'get-allowed-ac-charge-currents':
            return self.format_list(ac_charge_currents, fmt)

        elif c == 'set-max-ac-charge-current':
            if int(args[0]) != 0:
                raise ValueError(f'invalid machine id: {args[0]}')
            amps = int(args[1])
            if amps not in ac_charge_currents:
                raise ValueError(f'invalid value: {amps}')
            self.rated['max_ac_charge_current']['value'] = amps

        elif c == 'set-charge-thresholds':
            self.rated['battery_recharge_voltage']['value'] = float(args[0])
            self.rated['battery_redischarge_voltage']['value'] = float(args[1])

        elif c == 'set-output-source-priority':
            self.rated['output_source_priority'] = OutputSourcePriority.SolarBatteryUtility if args[0] == 'SBU' else OutputSourcePriority.SolarUtilityBattery

        elif c == 'set-battery-cutoff-voltage':
            self.rated['battery_under_voltage']['value'] = float(args[0])

        elif c == 'set-flag':
            flag = args[0]
            val = bool(int(args[1]))

            if flag == 'BUZZ':
                k = 'buzzer'
            elif flag == 'OLBP':
                k = 'overload_bypass'
            elif flag == 'LCDE':
                k = 'escape_to_default_screen_after_1min_timeout'
            elif flag == 'OLRS':
                k = 'overload_restart'
            elif flag == 'OTRS':
                k = 'over_temp_restart'
            elif flag == 'BLON':
                k = 'backlight_on'
            elif flag == 'ALRM':
                k = 'alarm_on_on_primary_source_interrupt'
            elif flag == 'FTCR':
                k = 'fault_code_record'
            else:
                raise ValueError('invalid flag')

            self.flags[k] = val

        else:
            raise ValueError(f'{c}: unsupported command')

    @staticmethod
    def format_list(values: list, fmt: Format) -> Union[str, list]:
        if fmt in (Format.JSON, Format.SIMPLE_JSON):
            return values
        return '\n'.join(map(lambda v: str(v), values))

    @staticmethod
    def format_dict(data: dict, fmt: Format) -> Union[str, dict]:
        new_data = {}
        for k, v in data.items():
            new_val = None
            if fmt in (Format.JSON, Format.TABLE, Format.SIMPLE_TABLE):
                if isinstance(v, dict):
                    new_val = v
                elif isinstance(v, InverterEnum):
                    new_val = v.as_text()
                else:
                    new_val = v
            elif fmt == Format.SIMPLE_JSON:
                if isinstance(v, dict):
                    new_val = v['value']
                elif isinstance(v, InverterEnum):
                    new_val = v.value
                else:
                    new_val = str(v)
            new_data[k] = new_val

        if fmt in (Format.JSON, Format.SIMPLE_JSON):
            return new_data

        lines = []

        if fmt == Format.SIMPLE_TABLE:
            for k, v in new_data.items():
                buf = k
                if isinstance(v, dict):
                    buf += ' ' + str(v['value']) + ' ' + v['unit']
                elif isinstance(v, InverterEnum):
                    buf += ' ' + v.as_text()
                else:
                    buf += ' ' + str(v)
                lines.append(buf)

        elif fmt == Format.TABLE:
            max_k_len = 0
            for k in new_data.keys():
                if len(_g_human_readable[k]) > max_k_len:
                    max_k_len = len(_g_human_readable[k])
            for k, v in new_data.items():
                buf = _g_human_readable[k] + ':'
                buf += ' ' * (max_k_len - len(_g_human_readable[k]) + 1)
                if isinstance(v, dict):
                    buf += str(v['value']) + ' ' + v['unit']
                elif isinstance(v, InverterEnum):
                    buf += v.as_text()
                elif isinstance(v, bool):
                    buf += str(int(v))
                else:
                    buf += str(v)
                lines.append(buf)

        return '\n'.join(lines)
