import time
import logging

from mysql.connector import connect, MySQLConnection, Error
from typing import Optional
from ..config import config

link: Optional[MySQLConnection] = None
logger = logging.getLogger(__name__)

datetime_fmt = '%Y-%m-%d %H:%M:%S'


def get_mysql() -> MySQLConnection:
    global link

    if link is not None:
        return link

    link = connect(
        host=config['mysql']['host'],
        user=config['mysql']['user'],
        password=config['mysql']['password'],
        database=config['mysql']['database'],
    )
    link.time_zone = '+01:00'
    return link


def mysql_now() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S')


class MySQLDatabase:
    def __init__(self):
        self.db = get_mysql()

    def cursor(self, **kwargs):
        try:
            self.db.ping(reconnect=True, attempts=2)
        except Error as e:
            logger.exception(e)
            self.db = get_mysql()
        return self.db.cursor(**kwargs)

    def commit(self):
        self.db.commit()
