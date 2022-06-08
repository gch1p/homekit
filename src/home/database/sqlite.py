import sqlite3
import os.path
import logging

from ..config import config, is_development_mode


def _get_database_path(name) -> str:
    return os.path.join(os.environ['HOME'], '.config', name, 'bot.db')


class SQLiteBase:
    SCHEMA = 1

    def __init__(self, name=None, check_same_thread=False):
        if not name:
            name = config.app_name

        self.logger = logging.getLogger(self.__class__.__name__)
        self.sqlite = sqlite3.connect(_get_database_path(name),
                                      check_same_thread=check_same_thread)

        if is_development_mode():
            self.sql_logger = logging.getLogger(self.__class__.__name__)
            self.sql_logger.setLevel('TRACE')
            self.sqlite.set_trace_callback(self.sql_logger.trace)

        sqlite_version = self._get_sqlite_version()
        self.logger.debug(f'SQLite version: {sqlite_version}')

        schema_version = self.schema_get_version()
        self.logger.debug(f'Schema version: {schema_version}')

        self.schema_init(schema_version)
        self.schema_set_version(self.SCHEMA)

    def __del__(self):
        if self.sqlite:
            self.sqlite.commit()
            self.sqlite.close()

    def _get_sqlite_version(self) -> str:
        cursor = self.sqlite.cursor()
        cursor.execute("SELECT sqlite_version()")
        return cursor.fetchone()[0]

    def schema_get_version(self) -> int:
        cursor = self.sqlite.execute('PRAGMA user_version')
        return int(cursor.fetchone()[0])

    def schema_set_version(self, v) -> None:
        self.sqlite.execute('PRAGMA user_version={:d}'.format(v))
        self.logger.info(f'Schema set to {v}')

    def cursor(self) -> sqlite3.Cursor:
        return self.sqlite.cursor()

    def commit(self) -> None:
        return self.sqlite.commit()

    def schema_init(self, version: int) -> None:
        raise ValueError(f'{self.__class__.__name__}: must override schema_init')
