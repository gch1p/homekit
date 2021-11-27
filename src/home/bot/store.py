import sqlite3
import os.path
import logging

from ..config import config

logger = logging.getLogger(__name__)


def _get_database_path() -> str:
    return os.path.join(os.environ['HOME'], '.config', config.app_name, 'bot.db')


class Store:
    SCHEMA_VERSION = 1

    def __init__(self):
        self.sqlite = sqlite3.connect(_get_database_path(), check_same_thread=False)

        sqlite_version = self._get_sqlite_version()
        logger.info(f'SQLite version: {sqlite_version}')

        schema_version = self._get_schema_version()
        logger.info(f'Schema version: {schema_version}')

        if schema_version < 1:
            self._database_init()
        elif schema_version < Store.SCHEMA_VERSION:
            self._database_upgrade(Store.SCHEMA_VERSION)

    def __del__(self):
        if self.sqlite:
            self.sqlite.commit()
            self.sqlite.close()

    def _get_sqlite_version(self) -> str:
        cursor = self.sqlite.cursor()
        cursor.execute("SELECT sqlite_version()")

        return cursor.fetchone()[0]
        
    def _get_schema_version(self) -> int:
        cursor = self.sqlite.execute('PRAGMA user_version')
        return int(cursor.fetchone()[0])

    def _set_schema_version(self, v) -> None:
        self.sqlite.execute('PRAGMA user_version={:d}'.format(v))
        logger.info(f'Schema set to {v}')

    def _database_init(self) -> None:
        cursor = self.sqlite.cursor()
        cursor.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            lang TEXT NOT NULL
        )""")
        self.sqlite.commit()
        self._set_schema_version(1)

    def _database_upgrade(self, version: int) -> None:
        # do the upgrade here

        # self.sqlite.commit()
        self._set_schema_version(version)

    def get_user_lang(self, user_id: int, default: str = 'en') -> str:
        cursor = self.sqlite.cursor()
        cursor.execute('SELECT lang FROM users WHERE id=?', (user_id,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute('INSERT INTO users (id, lang) VALUES (?, ?)', (user_id, default))
            self.sqlite.commit()
            return default
        else:
            return row[0]

    def set_user_lang(self, user_id: int, lang: str) -> None:
        cursor = self.sqlite.cursor()
        cursor.execute('UPDATE users SET lang=? WHERE id=?', (lang, user_id))
        self.sqlite.commit()