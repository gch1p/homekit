local worker config example:
```
api_url=http://ip:port
camera=1
threshold=1
```

remote worker config example:
```
api_url=http://ip:port
camera=1
threshold=1
fs_root=/var/ipcam_motion_fs
fs_max_filesize=146800640
```

optional fields:
```
roi_file=roi.txt
```

`/var/ipcam_motion_fs` should be a tmpfs mountpoint