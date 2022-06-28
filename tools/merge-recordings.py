#!/usr/bin/env python3
import os
import re
import subprocess
import tempfile
import sys

from typing import List
from datetime import datetime, timedelta
from argparse import ArgumentParser


fmt = '%d%m%y-%H%M%S'

File = dict
FileList = List[File]


def get_files(source_directory: str) -> FileList:
    files = []
    for f in os.listdir(source_directory):
        m = re.match(r'^(\d{6}-\d{6})_(\d{6}-\d{6})_id(\d+)(_\w+)?\.mp3$', f)
        if not m:
            continue

        files.append({
            'filename': os.path.join(source_directory, f),
            'start': datetime.strptime(m.group(1), fmt),
            'stop':  datetime.strptime(m.group(2), fmt)
        })
    files.sort(key=lambda f: f['start'].timestamp())
    return files


def group_files(files: FileList) -> List[FileList]:
    groups = []
    group_idx = None
    
    for info in files:
        # if group_idx is not None:
        #     print(info['start'], groups[group_idx][-1]['stop'])
        #     print('    ', info['start'] - groups[group_idx][-1]['stop'])
        #     print()

        if group_idx is None or \
                not groups[group_idx] or \
                info['start'] - groups[group_idx][-1]['stop'] <= timedelta(seconds=1):
            if group_idx is None:
                groups.append([])
                group_idx = 0
        else:
            group_idx += 1
            groups.append([])
        groups[group_idx].append(info)

    return groups


def merge(groups: List[FileList],
          output_directory: str,
          delete_source_files=False,
          vbr=False) -> None:
    for g in groups:
        success = False

        fd = tempfile.NamedTemporaryFile(delete=False)
        try:
            for file in g:
                line = f'file \'{file["filename"]}\'\n'
                # print(line.strip())
                fd.write(line.encode())
            fd.close()

            start = g[0]['start'].strftime(fmt)
            stop = g[-1]['stop'].strftime(fmt)
            fn = f'{start}_{stop}_merged.mp3'
            output = os.path.join(output_directory, fn)

            cmd = ['ffmpeg', '-y',
                   '-f', 'concat',
                   '-safe', '0',
                   '-i', fd.name,
                   '-map_metadata', '-1',
                   '-codec:a', 'libmp3lame']
            if vbr:
                cmd.extend(['-codec:a', 'libmp3lame', '-q:a', '4'])
            else:
                cmd.extend(['-codec:a', 'copy'])
            cmd.append(output)

            p = subprocess.run(cmd, capture_output=False)
            if p.returncode != 0:
                print(f'error: ffmpeg returned {p.returncode}')
            else:
                success = True
        finally:
            os.unlink(fd.name)

        if success and delete_source_files:
            for file in g:
                os.unlink(file['filename'])


def main():
    default_dir = os.getcwd()

    parser = ArgumentParser()
    parser.add_argument('--input-directory', '-i', type=str, default=default_dir,
                        help='Directory with files')
    parser.add_argument('--output-directory', '-o', type=str, default=default_dir,
                        help='Output directory')
    parser.add_argument('-D', '--delete-source-files', action='store_true')
    parser.add_argument('--vbr', action='store_true',
                        help='Re-encode using VBR (-q:a 4)')
    args = parser.parse_args()

    files = get_files(os.path.realpath(args.input_directory))
    if not len(files):
        print(f"No mp3 files found in {args.input_directory}.")
        sys.exit()

    groups = group_files(files)

    merge(groups,
          os.path.realpath(args.output_directory),
          delete_source_files=args.delete_source_files,
          vbr=args.vbr)


if __name__ == '__main__':
    main()
