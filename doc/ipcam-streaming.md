Let's assume IP cameras stream h264 via rtsp.

To `/etc/fstab`:
```
tmpfs /var/ipcamfs tmpfs mode=1755,uid=1000,gid=1000 0 0
```

For event-based FTP storage:
```
apt install vsftpd
```

`/etc/vsftpd.conf`:
```
chroot_local_user=YES
allow_writeable_chroot=YES

write_enable=YES
seccomp_sandbox=NO
```