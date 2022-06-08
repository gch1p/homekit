from ..database.sqlite import SQLiteBase


class Store(SQLiteBase):
    def __init__(self):
        super().__init__()

    def schema_init(self, version: int) -> None:
        if version < 1:
            cursor = self.cursor()
            cursor.execute("""CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                lang TEXT NOT NULL
            )""")
            self.commit()

    def get_user_lang(self, user_id: int, default: str = 'en') -> str:
        cursor = self.cursor()
        cursor.execute('SELECT lang FROM users WHERE id=?', (user_id,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute('INSERT INTO users (id, lang) VALUES (?, ?)', (user_id, default))
            self.commit()
            return default
        else:
            return row[0]

    def set_user_lang(self, user_id: int, lang: str) -> None:
        cursor = self.cursor()
        cursor.execute('UPDATE users SET lang=? WHERE id=?', (lang, user_id))
        self.commit()
