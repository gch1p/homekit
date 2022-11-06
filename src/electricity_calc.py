#!/usr/bin/env python3
import logging
import os
import sys
import inspect
import zoneinfo

from home.config import config  # do not remove this import!
from datetime import datetime, timedelta
from logging import Logger
from home.database import InverterDatabase
from argparse import ArgumentParser, ArgumentError
from typing import Optional

_logger: Optional[Logger] = None
_progname = os.path.basename(__file__)
_is_verbose = False

fmt_time = '%Y-%m-%d %H:%M:%S'
fmt_date = '%Y-%m-%d'


def method_usage() -> str:
    # https://stackoverflow.com/questions/2654113/how-to-get-the-callers-method-name-in-the-called-method
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    return f'{_progname} {calframe[1][3]} [ARGS]'


def fmt_escape(s: str):
    return s.replace('%', '%%')


def setup_logging(verbose: bool):
    global _is_verbose

    logging_level = logging.INFO if not verbose else logging.DEBUG
    logging.basicConfig(level=logging_level)

    _is_verbose = verbose


class SubParser:
    def __init__(self, description: str, usage: str):
        self.parser = ArgumentParser(
            description=description,
            usage=usage
        )

    def add_argument(self, *args, **kwargs):
        self.parser.add_argument(*args, **kwargs)

    def parse_args(self):
        self.add_argument('--verbose', '-V', action='store_true',
                          help='enable debug logs')

        args = self.parser.parse_args(sys.argv[2:])
        setup_logging(args.verbose)

        return args


def strptime_auto(s: str) -> datetime:
    e = None
    for fmt in (fmt_time, fmt_date):
        try:
            return datetime.strptime(s, fmt)
        except ValueError as _e:
            e = _e
    raise e


def get_dt_from_to_arguments(parser):
    parser.add_argument('--from', type=str, dest='date_from', required=True,
                        help=f'From date, format: {fmt_escape(fmt_time)} or {fmt_escape(fmt_date)}')
    parser.add_argument('--to', type=str, dest='date_to', default='now',
                        help=f'To date, format: {fmt_escape(fmt_time)}, {fmt_escape(fmt_date)}, \'now\' or \'24h\'')
    arg = parser.parse_args()

    dt_from = strptime_auto(arg.date_from)

    if arg.date_to == 'now':
        dt_to = datetime.now()
    elif arg.date_to == '24h':
        dt_to = dt_from + timedelta(days=1)
    else:
        dt_to = strptime_auto(arg.date_to)

    return dt_from, dt_to


def print_intervals(intervals):
    for interval in intervals:
        start, end = interval
        buf = f'{start.strftime(fmt_time)} .. '
        if end:
            buf += f'{end.strftime(fmt_time)}'
        else:
            buf += 'now'

        print(buf)


class Electricity():
    def __init__(self):
        global _logger

        methods = [func.replace('_', '-')
                   for func in dir(Electricity)
                   if callable(getattr(Electricity, func)) and not func.startswith('_') and func != 'query']

        parser = ArgumentParser(
            usage=f'{_progname} METHOD [ARGS]'
        )
        parser.add_argument('method', choices=methods,
                            help='Method to run')
        parser.add_argument('--verbose', '-V', action='store_true',
                            help='enable debug logs')

        argv = sys.argv[1:2]
        for arg in ('-V', '--verbose'):
            if arg in sys.argv:
                argv.append(arg)
        args = parser.parse_args(argv)

        setup_logging(args.verbose)
        self.db = InverterDatabase()

        method = args.method.replace('-', '_')
        getattr(self, method)()

    def get_grid_connected_intervals(self):
        parser = SubParser('Returns datetime intervals when grid was connected', method_usage())
        dt_from, dt_to = get_dt_from_to_arguments(parser)

        intervals = self.db.get_grid_connected_intervals(dt_from, dt_to)
        print_intervals(intervals)

    def get_grid_used_intervals(self):
        parser = SubParser('Returns datetime intervals when power grid was actually used', method_usage())
        dt_from, dt_to = get_dt_from_to_arguments(parser)

        intervals = self.db.get_grid_used_intervals(dt_from, dt_to)
        print_intervals(intervals)

    def get_grid_consumed_energy(self):
        parser = SubParser('Returns sum of energy consumed from util grid', method_usage())
        dt_from, dt_to = get_dt_from_to_arguments(parser)

        wh = self.db.get_grid_consumed_energy(dt_from, dt_to)
        print('%.2f' % wh,)

    def get_consumed_energy(self):
        parser = SubParser('Returns total consumed energy', method_usage())
        dt_from, dt_to = get_dt_from_to_arguments(parser)

        wh = self.db.get_consumed_energy(dt_from, dt_to)
        print('%.2f' % wh,)


if __name__ == '__main__':
    try:
        Electricity()
    except Exception as e:
        _logger.exception(e)
        sys.exit(1)
