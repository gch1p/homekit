#!/usr/bin/env python3
import os
import re
import subprocess
import tempfile
import sys

from datetime import datetime, timedelta
from argparse import ArgumentParser


input_fmt = '%Y-%m-%d-%H:%M:%S.%f'
output_fmt = '%Y-%m-%d-%H:%M:%S'

# declare types
File = dict
FileList = list[File]


def get_files(source_directory: str) -> FileList:
    files = []
    for f in os.listdir(source_directory):
        # 2022-06-15-00:02:40.187877.jpg
        m = re.match(r'(^\d{4}-\d{2}-\d{2}-\d{2}:\d{2}:\d{2}\.\d{1,6})\.jpg$', f)
        if not m:
            continue

        files.append({
            'filename': os.path.join(source_directory, f),
            'time': datetime.strptime(m.group(1), input_fmt),
        })
    files.sort(key=lambda f: f['time'].timestamp())
    return files


def group_files(files: FileList) -> list[FileList]:
    groups = []
    group_idx = None

    for file in files:
        if group_idx is None or \
                not groups[group_idx] or \
                file['time'] - groups[group_idx][-1]['time'] <= timedelta(seconds=10):
            if group_idx is None:
                groups.append([])
                group_idx = 0
        else:
            group_idx += 1
            groups.append([])
        groups[group_idx].append(file)

    return groups


def merge(groups: list[FileList],
          output_directory: str,
          delete_source_files=False,
          cedrus=False) -> None:
    for g in groups:
        success = False

        fd = tempfile.NamedTemporaryFile(delete=False)
        try:
            n = len(g)
            last_frame_dur = 0
            for i in range(n):
                file = g[i]
                fd.write(f'file \'{file["filename"]}\'\n'.encode())

                if i < n-1:
                    last_frame_dur = g[i+1]['time'].timestamp()-file['time'].timestamp()

                fd.write(f'duration {last_frame_dur}\n'.encode())
            fd.close()
            print(f'temp concat file: {fd.name}')

            start = g[0]['time'].strftime(output_fmt)
            stop = g[-1]['time'].strftime(output_fmt)

            fn = f'{start}_{stop}_merged.mp4'
            output = os.path.join(output_directory, fn)

            if cedrus:
                ffmpeg = '/home/user/.local/bin/ffmpeg-cedrus'
                env = dict(os.environ)
                env['LD_LIBRARY_PATH'] = '/usr/local/lib'
                args = ['-c:v', 'cedrus264',
                        '-pix_fmt', 'nv12']
            else:
                ffmpeg = 'ffmpeg'
                env = {}
                args = ['-c:v', 'libx264',
                        '-preset', 'veryslow',
                        # '-crf', '23',
                        # '-vb', '448k',
                        '-filter:v', 'fps=2']

            cmd = [ffmpeg, '-y',
                   '-f', 'concat',
                   '-safe', '0',
                   '-i', fd.name,
                   '-map_metadata', '-1',
                   *args,
                   output]

            p = subprocess.run(cmd, capture_output=False, env=env)
            if p.returncode != 0:
                print(f'error: ffmpeg returned {p.returncode}')
            else:
                success = True
        finally:
            os.unlink(fd.name)

        if success and delete_source_files:
            for file in g:
                os.unlink(file['filename'])


def print_groups(groups):
    for g in groups:
        g1 = g[0]
        g2 = g[len(g)-1]
        print(str(g1['time'])+' .. '+str(g2['time']))


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--input-directory', '-i', type=str, required=True,
                        help='Directory with files')
    parser.add_argument('--output-directory', '-o', type=str, required=True,
                        help='Output directory')
    parser.add_argument('-D', '--delete-source-files', action='store_true')
    parser.add_argument('--cedrus', action='store_true')
    # parser.add_argument('--vbr', action='store_true',
    #                     help='Re-encode using VBR (-q:a 4)')
    arg = parser.parse_args()

    # if arg.cedrus and not os.getegid() == 0:
    #     raise RuntimeError("Must be run as root.")

    files = get_files(os.path.realpath(arg.input_directory))
    if not len(files):
        print(f"No jpeg files found in {arg.input_directory}.")
        sys.exit()

    groups = group_files(files)
    # print_groups(groups)

    merge(groups,
          os.path.realpath(arg.output_directory),
          delete_source_files=arg.delete_source_files,
          cedrus=arg.cedrus)
