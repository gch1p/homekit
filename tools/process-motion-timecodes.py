#!/usr/bin/env python3
import os.path

from argparse import ArgumentParser
from datetime import datetime, timedelta

DATETIME_FORMAT = '%Y-%m-%d-%H.%M.%S'


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def time2seconds(time: str) -> int:
    time, frac = time.split('.')
    frac = int(frac)

    h, m, s = [int(i) for i in time.split(':')]

    return round(s + m*60 + h*3600 + frac/1000)


def filename_to_datetime(filename: str) -> datetime:
    filename = os.path.basename(filename).replace('record_', '').replace('.mp4', '')
    return datetime.strptime(filename, DATETIME_FORMAT)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--source-filename', type=str, required=True,
                        help='recording filename')
    parser.add_argument('--timecodes', type=str, required=True,
                        help='timecodes')
    parser.add_argument('--padding', type=int, default=2,
                        help='amount of seconds to add before and after each fragment')
    arg = parser.parse_args()

    if arg.padding < 0:
        raise ValueError('invalid padding')

    timecodes = arg.timecodes.split(',')
    if len(timecodes) % 2 != 0:
        raise ValueError('invalid number of timecodes')

    timecodes = list(map(time2seconds, timecodes))
    timecodes = list(chunks(timecodes, 2))

    # sort out invalid fragments (dvr-scan returns them sometimes, idk why...)
    timecodes = list(filter(lambda f: f[0] < f[1], timecodes))

    file_dt = filename_to_datetime(arg.source_filename)

    # https://stackoverflow.com/a/43600953
    timecodes.sort(key=lambda interval: interval[0])
    merged = [timecodes[0]]
    for current in timecodes:
        previous = merged[-1]
        if current[0] <= previous[1]:
            previous[1] = max(previous[1], current[1])
        else:
            merged.append(current)

    for fragment in merged:
        start, end = fragment

        start -= arg.padding
        end += arg.padding

        if start < 0:
            start = 0

        duration = end - start

        dt1 = (file_dt + timedelta(seconds=start)).strftime(DATETIME_FORMAT)
        dt2 = (file_dt + timedelta(seconds=end)).strftime(DATETIME_FORMAT)
        filename = f'{dt1}__{dt2}.mp4'

        print(f'{start} {duration} {filename}')
