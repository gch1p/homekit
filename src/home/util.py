import functools
import json
import socket
import time
import requests
import subprocess
import traceback
import logging
import string
import random
import asyncio

from enum import Enum
from .config import config
from datetime import datetime
from typing import Tuple, Optional

Addr = Tuple[str, int]  # network address type (host, port)

logger = logging.getLogger(__name__)


# https://stackoverflow.com/questions/312443/how-do-you-split-a-list-into-evenly-sized-chunks
def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def json_serial(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.timestamp()
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError("Type %s not serializable" % type(obj))


def stringify(v) -> str:
    return json.dumps(v, separators=(',', ':'), default=json_serial)


def ipv4_valid(ip: str) -> bool:
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def parse_addr(addr: str) -> Addr:
    if addr.count(':') != 1:
        raise ValueError('invalid host:port format')

    host, port = addr.split(':')
    if not ipv4_valid(host):
        raise ValueError('invalid ipv4 address')

    port = int(port)
    if not 0 <= port <= 65535:
        raise ValueError('invalid port')

    return host, port


def strgen(n: int):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))


class MySimpleSocketClient:
    host: str
    port: int

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(5)

    def __del__(self):
        self.sock.close()

    def write(self, line: str) -> None:
        self.sock.sendall((line + '\r\n').encode())

    def read(self) -> str:
        buf = bytearray()
        while True:
            buf.extend(self.sock.recv(256))
            if b'\r\n' in buf:
                break

        response = buf.decode().strip()
        return response


def send_datagram(message: str, addr: Addr) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(message.encode(), addr)


def send_telegram(text: str,
                  parse_mode: str = None,
                  disable_web_page_preview: bool = False):
    data, token = _send_telegram_data(text, parse_mode, disable_web_page_preview)
    r = requests.post('https://api.telegram.org/bot%s/sendMessage' % token, data=data)
    if r.status_code != 200:
        logger.error(r.text)
        raise RuntimeError("telegram returned %d" % r.status_code)


async def send_telegram_aio(text: str,
                            parse_mode: str = None,
                            disable_web_page_preview: bool = False):
    loop = asyncio.get_event_loop()
    data, token = _send_telegram_data(text, parse_mode, disable_web_page_preview)
    r = await loop.run_in_executor(None,
                                   functools.partial(requests.post,
                                                     'https://api.telegram.org/bot%s/sendMessage' % token,
                                                     data=data))
    if r.status_code != 200:
        logger.error(r.text)
        raise RuntimeError("telegram returned %d" % r.status_code)


def _send_telegram_data(text: str,
                        parse_mode: str = None,
                        disable_web_page_preview: bool = False) -> tuple[dict, str]:
    data = {
        'chat_id': config['telegram']['chat_id'],
        'text': text
    }

    if parse_mode is not None:
        data['parse_mode'] = parse_mode
    elif 'parse_mode' in config['telegram']:
        data['parse_mode'] = config['telegram']['parse_mode']

    if disable_web_page_preview or 'disable_web_page_preview' in config['telegram']:
        data['disable_web_page_preview'] = 1

    return data, config['telegram']['token']


def format_tb(exc) -> Optional[list[str]]:
    tb = traceback.format_tb(exc.__traceback__)
    if not tb:
        return None

    tb = list(map(lambda s: s.strip(), tb))
    tb.reverse()
    if tb[0][-1:] == ':':
        tb[0] = tb[0][:-1]

    return tb


class ChildProcessInfo:
    pid: int
    cmd: str

    def __init__(self,
                 pid: int,
                 cmd: str):
        self.pid = pid
        self.cmd = cmd


def find_child_processes(ppid: int) -> list[ChildProcessInfo]:
    p = subprocess.run(['pgrep', '-P', str(ppid), '--list-full'], capture_output=True)
    if p.returncode != 0:
        raise OSError(f'pgrep returned {p.returncode}')

    children = []

    lines = p.stdout.decode().strip().split('\n')
    for line in lines:
        try:
            space_idx = line.index(' ')
        except ValueError as exc:
            logger.exception(exc)
            continue

        pid = int(line[0:space_idx])
        cmd = line[space_idx+1:]

        children.append(ChildProcessInfo(pid, cmd))

    return children


class Stopwatch:
    elapsed: float
    time_started: Optional[float]

    def __init__(self):
        self.elapsed = 0
        self.time_started = None

    def go(self):
        if self.time_started is not None:
            raise StopwatchError('stopwatch was already started')

        self.time_started = time.time()

    def pause(self):
        if self.time_started is None:
            raise StopwatchError('stopwatch was paused')

        self.elapsed += time.time() - self.time_started
        self.time_started = None

    def get_elapsed_time(self):
        elapsed = self.elapsed
        if self.time_started is not None:
            elapsed += time.time() - self.time_started
        return elapsed

    def reset(self):
        self.time_started = None
        self.elapsed = 0

    def is_paused(self):
        return self.time_started is None


class StopwatchError(RuntimeError):
    pass


def filesize_fmt(num, suffix="B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"