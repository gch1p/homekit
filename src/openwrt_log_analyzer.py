#!/usr/bin/env python3
import home.telegram as telegram

from home.config import config
from home.database import BotsDatabase, SimpleState

"""
config.toml example:

[simple_state]
file = "/home/user/.config/openwrt_log_analyzer/state.txt"

[mysql]
host = "localhost"
database = ".."
user = ".."
password = ".."

[devices]
Device1 = "00:00:00:00:00:00"
Device2 = "01:01:01:01:01:01"

[telegram]
chat_id = ".."
token = ".."
parse_mode = "HTML"

[openwrt_log_analyzer]
limit = 10
"""


def main(mac: str, title: str) -> int:
    db = BotsDatabase()

    data = db.get_openwrt_logs(filter_text=mac,
                               min_id=state['last_id'],
                               limit=config['openwrt_log_analyzer']['limit'])
    if not data:
        return 0

    max_id = 0
    for log in data:
        if log.id > max_id:
            max_id = log.id

    text = '\n'.join(map(lambda s: str(s), data))
    telegram.send_message(f'<b>{title}</b>\n\n' + text)

    return max_id


if __name__ == '__main__':
    config.load('openwrt_log_analyzer')

    state = SimpleState(file=config['simple_state']['file'],
                        default={'last_id': 0})

    max_last_id = 0
    for name, mac in config['devices'].items():
        last_id = main(mac, title=name)
        if last_id > max_last_id:
            max_last_id = last_id

    if max_last_id:
        state['last_id'] = max_last_id
