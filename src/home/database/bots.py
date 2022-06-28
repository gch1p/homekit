import pytz

from .mysql import mysql_now, MySQLDatabase, datetime_fmt
from ..api.types import (
    BotType,
    SoundSensorLocation
)
from typing import Optional, List, Tuple
from datetime import datetime
from html import escape


class OpenwrtLogRecord:
    id: int
    log_time: datetime
    received_time: datetime
    text: str

    def __init__(self, id, text, log_time, received_time):
        self.id = id
        self.text = text
        self.log_time = log_time
        self.received_time = received_time

    def __repr__(self):
        return f"<b>{self.log_time.strftime('%H:%M:%S')}</b> {escape(self.text)}"


class BotsDatabase(MySQLDatabase):
    def add_request(self,
                    bot: BotType,
                    user_id: int,
                    message: str):
        with self.cursor() as cursor:
            cursor.execute("INSERT INTO requests_log (user_id, message, bot, time) VALUES (%s, %s, %s, %s)",
                           (user_id, message, bot.name.lower(), mysql_now()))
        self.commit()

    def add_openwrt_logs(self,
                         lines: List[Tuple[datetime, str]]):
        now = datetime.now()
        with self.cursor() as cursor:
            for line in lines:
                time, text = line
                cursor.execute("INSERT INTO openwrt (log_time, received_time, text) VALUES (%s, %s, %s)",
                               (time.strftime(datetime_fmt), now.strftime(datetime_fmt), text))
        self.commit()

    def add_sound_hits(self,
                       hits: List[Tuple[SoundSensorLocation, int]],
                       time: datetime):
        with self.cursor() as cursor:
            for loc, count in hits:
                cursor.execute("INSERT INTO sound_hits (location, `time`, hits) VALUES (%s, %s, %s)",
                               (loc.name.lower(), time.strftime(datetime_fmt), count))
            self.commit()

    def get_sound_hits(self,
                       location: SoundSensorLocation,
                       after: Optional[datetime] = None,
                       last: Optional[int] = None) -> List[dict]:
        with self.cursor(dictionary=True) as cursor:
            sql = "SELECT `time`, hits FROM sound_hits WHERE location=%s"
            args = [location.name.lower()]

            if after:
                sql += ' AND `time` >= %s ORDER BY time DESC'
                args.append(after)
            elif last:
                sql += ' ORDER BY time DESC LIMIT 0, %s'
                args.append(last)
            else:
                raise ValueError('no `after`, no `last`, what do you expect?')

            cursor.execute(sql, tuple(args))
            data = []
            for row in cursor.fetchall():
                data.append({
                    'time': row['time'],
                    'hits': row['hits']
                })
            return data

    def get_openwrt_logs(self,
                         filter_text: str,
                         min_id: int,
                         limit: int = None) -> List[OpenwrtLogRecord]:
        tz = pytz.timezone('Europe/Moscow')
        with self.cursor(dictionary=True) as cursor:
            sql = "SELECT * FROM openwrt WHERE text LIKE %s AND id > %s"
            if limit is not None:
                sql += f" LIMIT {limit}"

            cursor.execute(sql, (f'%{filter_text}%', min_id))
            data = []
            for row in cursor.fetchall():
                data.append(OpenwrtLogRecord(
                    id=int(row['id']),
                    text=row['text'],
                    log_time=row['log_time'].astimezone(tz),
                    received_time=row['received_time'].astimezone(tz)
                ))

            return data
