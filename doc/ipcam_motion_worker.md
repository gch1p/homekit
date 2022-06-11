# ipcam_motion_worker.sh

One worker per camera.

## Usage

```
ipcam_motion_worker.sh [-v] [--allow-multiple] -c ~/.config/ipcam_motion_worker/1.txt
```

## Configuration

Local worker config example:
```
api_url=http://ip:port
camera=1
```

Remote worker config example:
```
remote=1
api_url=http://ip:port
camera=1
fs_root=/var/ipcam_motion_fs
fs_max_filesize=146800640
```

Optional fields (dvr-scan options):
```
roi_file=roi.txt
threshold=1
min_event_length=3s
downscale_factor=3
frame_skip=2
dvr_scan_path=
```

`api_url` must point to `ipcam_server` instance.

`/var/ipcam_motion_fs` should be a tmpfs mountpoint. Therefore, `/etc/fstab`:
```
tmpfs /var/ipcam_motion_fs tmpfs size=150M,mode=1755,uid=1000,gid=1000 0 0 
```

# ipcam_motion_worker_multiple.sh

This script just consequentially runs `ipcam_motion_worker.sh` with `-c ~/.config/ipcam_motion_worker/$NAME.txt` argument.

## Usage

```
ipcam_worker_worker_multiple.sh -v NAME NAME NAME ...
```

When launching by cron, set `TERM=xterm` and `PATH` (to your `$PATH`) variables in crontab.

# Dependencies

```
apt-get install python3-opencv
pip3 install dvr-scan
```

Then add to `~/.local/bin` to `$PATH`.
