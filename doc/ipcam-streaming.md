Let's assume IP cameras stream h264 via rtsp.

To `/etc/fstab`:
```
tmpfs /var/ipcamfs tmpfs mode=1755,uid=1000,gid=1000 0 0
```