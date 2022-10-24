import logging

from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from clickhouse_driver import Client as ClickhouseClient
from ..config import is_development_mode

_links = {}


def get_clickhouse(db: str) -> ClickhouseClient:
    if db not in _links:
        _links[db] = ClickhouseClient.from_url(f'clickhouse://localhost/{db}')

    return _links[db]


class ClickhouseDatabase:
    def __init__(self, db: str):
        self.db = get_clickhouse(db)

        self.server_timezone = self.db.execute('SELECT timezone()')[0][0]
        self.logger = logging.getLogger(self.__class__.__name__)

    def query(self, *args, **kwargs):
        settings = {'use_client_time_zone': True}
        kwargs['settings'] = settings

        if 'no_tz_fix' not in kwargs and len(args) > 1 and isinstance(args[1], dict):
            for k, v in args[1].items():
                if isinstance(v, datetime):
                    args[1][k] = v.astimezone(tz=ZoneInfo(self.server_timezone))

        result = self.db.execute(*args, **kwargs)

        if is_development_mode():
            self.logger.debug(args[0] if len(args) == 1 else args[0] % args[1])

        return result
