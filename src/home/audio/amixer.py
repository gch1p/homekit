import subprocess

from ..config import config
from threading import Lock
from typing import Union, List


_lock = Lock()
_default_step = 5


def has_control(s: str) -> bool:
    for control in config['amixer']['controls']:
        if control['name'] == s:
            return True
    return False


def get_caps(s: str) -> List[str]:
    for control in config['amixer']['controls']:
        if control['name'] == s:
            return control['caps']
    raise KeyError(f'control {s} not found')


def get_all() -> list:
    controls = []
    for control in config['amixer']['controls']:
        controls.append({
            'name': control['name'],
            'info': get(control['name']),
            'caps': control['caps']
        })
    return controls


def get(control: str):
    return call('get', control)


def mute(control):
    return call('set', control, 'mute')


def unmute(control):
    return call('set', control, 'unmute')


def cap(control):
    return call('set', control, 'cap')


def nocap(control):
    return call('set', control, 'nocap')


def _get_default_step() -> int:
    if 'step' in config['amixer']:
        return int(config['amixer']['step'])

    return _default_step


def incr(control, step=None):
    if step is None:
        step = _get_default_step()
    return call('set', control, f'{step}%+')


def decr(control, step=None):
    if step is None:
        step = _get_default_step()
    return call('set', control, f'{step}%-')


def call(*args, return_code=False) -> Union[int, str]:
    with _lock:
        result = subprocess.run([config['amixer']['bin'], *args],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        if return_code:
            return result.returncode

        if result.returncode != 0:
            raise AmixerError(result.stderr.decode().strip())

        return result.stdout.decode().strip()


class AmixerError(OSError):
    pass
