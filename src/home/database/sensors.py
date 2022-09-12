from time import time
from datetime import datetime
from typing import Tuple, List
from .clickhouse import get_clickhouse
from ..api.types import TemperatureSensorLocation


def get_temperature_table(sensor: TemperatureSensorLocation) -> str:
    if sensor == TemperatureSensorLocation.DIANA:
        return 'temp_diana'

    elif sensor == TemperatureSensorLocation.STREET:
        return 'temp_street'

    elif sensor == TemperatureSensorLocation.BIG_HOUSE_1:
        return 'temp'

    elif sensor == TemperatureSensorLocation.BIG_HOUSE_2:
        return 'temp_roof'

    elif sensor == TemperatureSensorLocation.BIG_HOUSE_ROOM:
        return 'temp_room'

    elif sensor == TemperatureSensorLocation.SPB1:
        return 'temp_spb1'


class SensorsDatabase:
    def __init__(self):
        self.db = get_clickhouse('home')

    def add_temperature(self,
                        home_id: int,
                        client_time: int,
                        sensor: TemperatureSensorLocation,
                        temp: int,
                        rh: int):
        table = get_temperature_table(sensor)
        sql = """INSERT INTO """ + table + """ (
                        ClientTime,
                        ReceivedTime,
                        HomeID,
                        Temperature,
                        RelativeHumidity
                        ) VALUES"""
        self.db.execute(sql, [[
            client_time,
            int(time()),
            home_id,
            temp,
            rh
        ]])

    def get_temperature_recordings(self,
                                   sensor: TemperatureSensorLocation,
                                   time_range: Tuple[datetime, datetime],
                                   home_id=1) -> List[tuple]:
        table = get_temperature_table(sensor)
        sql = f"""SELECT ClientTime, Temperature, RelativeHumidity 
            FROM {table}
            WHERE ClientTime >= %(from)s AND ClientTime <= %(to)s
            ORDER BY ClientTime"""
        dt_from, dt_to = time_range

        data = self.db.execute(sql, {
            'from': dt_from,
            'to': dt_to
        })
        return [(date, temp/100, humidity/100) for date, temp, humidity in data]
