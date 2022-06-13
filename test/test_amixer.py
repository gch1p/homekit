#!/usr/bin/env python3
import sys, os.path
sys.path.extend([
    os.path.realpath(os.path.join(os.path.dirname(os.path.join(__file__)), '..')),
])

from argparse import ArgumentParser
from src.home.config import config
from src.home.audio import amixer


def validate_control(input: str):
    for control in config['amixer']['controls']:
        if control['name'] == input:
            return
    raise ValueError(f'invalid control name: {input}')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--get-all', action='store_true')
    parser.add_argument('--mute', type=str)
    parser.add_argument('--unmute', type=str)
    parser.add_argument('--cap', type=str)
    parser.add_argument('--nocap', type=str)
    parser.add_argument('--get', type=str)
    parser.add_argument('--incr', type=str)
    parser.add_argument('--decr', type=str)
    # parser.add_argument('--dump-config', action='store_true')

    args = config.load('test_amixer', parser=parser)

    # if args.dump_config:
    #     print(config.data)
    #     sys.exit()

    if args.get_all:
        for control in amixer.get_all():
            print(f'control = {control["name"]}')
            for line in control['info'].split('\n'):
                print(f'    {line}')
            print()
        sys.exit()

    if args.get:
        info = amixer.get(args.get)
        print(info)
        sys.exit()

    for action in ['incr', 'decr']:
        if hasattr(args, action):
            control = getattr(args, action)
            if control is None:
                continue

            print(f'attempting to {action} {control}')
            validate_control(control)
            func = getattr(amixer, action)
            try:
                func(control, step=5)
            except amixer.AmixerError as e:
                print('error: ' + str(e))
            sys.exit()

    for action in ['mute', 'unmute', 'cap', 'nocap']:
        if hasattr(args, action):
            control = getattr(args, action)
            if control is None:
                continue

            print(f"attempting to {action} {control}")

            validate_control(control)
            func = getattr(amixer, action)
            try:
                func(control)
            except amixer.AmixerError as e:
                print('error: ' + str(e))
            sys.exit()
