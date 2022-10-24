from time import time
from datetime import datetime
from typing import Optional
from collections import namedtuple

from .clickhouse import ClickhouseDatabase


IntervalList = list[list[Optional[datetime]]]


class InverterDatabase(ClickhouseDatabase):
    def __init__(self):
        super().__init__('solarmon')

    def add_generation(self, home_id: int, client_time: int, watts: int) -> None:
        self.db.execute(
            'INSERT INTO generation (ClientTime, ReceivedTime, HomeID, Watts) VALUES',
            [[client_time, round(time()), home_id, watts]]
        )

    def add_status(self, home_id: int,
                   client_time: int,
                   grid_voltage: int,
                   grid_freq: int,
                   ac_output_voltage: int,
                   ac_output_freq: int,
                   ac_output_apparent_power: int,
                   ac_output_active_power: int,
                   output_load_percent: int,
                   battery_voltage: int,
                   battery_voltage_scc: int,
                   battery_voltage_scc2: int,
                   battery_discharge_current: int,
                   battery_charge_current: int,
                   battery_capacity: int,
                   inverter_heat_sink_temp: int,
                   mppt1_charger_temp: int,
                   mppt2_charger_temp: int,
                   pv1_input_power: int,
                   pv2_input_power: int,
                   pv1_input_voltage: int,
                   pv2_input_voltage: int,
                   mppt1_charger_status: int,
                   mppt2_charger_status: int,
                   battery_power_direction: int,
                   dc_ac_power_direction: int,
                   line_power_direction: int,
                   load_connected: int) -> None:
        self.db.execute("""INSERT INTO status (
            ClientTime,
            ReceivedTime,
            HomeID,
            GridVoltage,
            GridFrequency,
            ACOutputVoltage,
            ACOutputFrequency,
            ACOutputApparentPower,
            ACOutputActivePower,
            OutputLoadPercent,
            BatteryVoltage,
            BatteryVoltageSCC,
            BatteryVoltageSCC2,
            BatteryDischargingCurrent,
            BatteryChargingCurrent,
            BatteryCapacity,
            HeatSinkTemp,
            MPPT1ChargerTemp,
            MPPT2ChargerTemp,
            PV1InputPower,
            PV2InputPower,
            PV1InputVoltage,
            PV2InputVoltage,
            MPPT1ChargerStatus,
            MPPT2ChargerStatus,
            BatteryPowerDirection,
            DCACPowerDirection,
            LinePowerDirection,
            LoadConnected) VALUES""", [[
            client_time,
            round(time()),
            home_id,
            grid_voltage,
            grid_freq,
            ac_output_voltage,
            ac_output_freq,
            ac_output_apparent_power,
            ac_output_active_power,
            output_load_percent,
            battery_voltage,
            battery_voltage_scc,
            battery_voltage_scc2,
            battery_discharge_current,
            battery_charge_current,
            battery_capacity,
            inverter_heat_sink_temp,
            mppt1_charger_temp,
            mppt2_charger_temp,
            pv1_input_power,
            pv2_input_power,
            pv1_input_voltage,
            pv2_input_voltage,
            mppt1_charger_status,
            mppt2_charger_status,
            battery_power_direction,
            dc_ac_power_direction,
            line_power_direction,
            load_connected
        ]])

    def get_consumed_energy(self, dt_from: datetime, dt_to: datetime) -> float:
        rows = self.query('SELECT ClientTime, ACOutputActivePower FROM status'
                          ' WHERE ClientTime >= %(from)s AND ClientTime <= %(to)s'
                          ' ORDER BY ClientTime', {'from': dt_from, 'to': dt_to})
        prev_time = None
        prev_wh = 0

        ws = 0  # watt-seconds
        for t, wh in rows:
            if prev_time is not None:
                n = (t - prev_time).total_seconds()
                ws += prev_wh * n

            prev_time = t
            prev_wh = wh

        return ws / 3600  # convert to watt-hours

    def get_intervals_by_condition(self,
                                   dt_from: datetime,
                                   dt_to: datetime,
                                   cond_start: str,
                                   cond_end: str) -> IntervalList:
        rows = None
        ranges = [[None, None]]

        while rows is None or len(rows) > 0:
            if ranges[len(ranges)-1][0] is None:
                condition = cond_start
                range_idx = 0
            else:
                condition = cond_end
                range_idx = 1

            rows = self.query('SELECT ClientTime FROM status '
                              f'WHERE ClientTime > %(from)s AND ClientTime <= %(to)s AND {condition}'
                              ' ORDER BY ClientTime LIMIT 1',
                              {'from': dt_from, 'to': dt_to})
            if not rows:
                break

            row = rows[0]

            ranges[len(ranges) - 1][range_idx] = row[0]
            if range_idx == 1:
                ranges.append([None, None])

            dt_from = row[0]

        if ranges[len(ranges)-1][0] is None:
            ranges.pop()
        elif ranges[len(ranges)-1][1] is None:
            ranges[len(ranges)-1][1] = dt_to - timedelta(seconds=1)

        return ranges

    def get_grid_connected_intervals(self, dt_from: datetime, dt_to: datetime) -> IntervalList:
        return self.get_intervals_by_condition(dt_from, dt_to, 'GridFrequency > 0', 'GridFrequency = 0')

    def get_grid_used_intervals(self, dt_from: datetime, dt_to: datetime) -> IntervalList:
        return self.get_intervals_by_condition(dt_from,
                                               dt_to,
                                               "LinePowerDirection = 'Input'",
                                               "LinePowerDirection != 'Input'")

    def get_grid_consumed_energy(self, dt_from: datetime, dt_to: datetime) -> float:
        PrevData = namedtuple('PrevData', 'time, pd, bat_chg, bat_dis, wh')

        ws = 0  # watt-seconds
        amps = 0  # amper-seconds

        intervals = self.get_grid_used_intervals(dt_from, dt_to)
        for dt_start, dt_end in intervals:
            fields = ', '.join([
                'ClientTime',
                'DCACPowerDirection',
                'BatteryChargingCurrent',
                'BatteryDischargingCurrent',
                'ACOutputActivePower'
            ])
            rows = self.query(f'SELECT {fields} FROM status'
                              ' WHERE ClientTime >= %(from)s AND ClientTime < %(to)s ORDER BY ClientTime',
                              {'from': dt_start, 'to': dt_end})

            prev = PrevData(time=None, pd=None, bat_chg=None, bat_dis=None, wh=None)
            for ct, pd, bat_chg, bat_dis, wh in rows:
                if prev.time is not None:
                    n = (ct-prev.time).total_seconds()
                    ws += prev.wh * n

                    if pd == 'DC/AC':
                        amps -= prev.bat_dis * n
                    elif pd == 'AC/DC':
                        amps += prev.bat_chg * n

                prev = PrevData(time=ct, pd=pd, bat_chg=bat_chg, bat_dis=bat_dis, wh=wh)

        amps /= 3600
        wh = ws / 3600
        wh += amps*48

        return wh
