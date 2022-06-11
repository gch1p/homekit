## Dependencies

- `ffmpeg`

## HLS

Let's assume IP cameras stream h264 via rtsp.

- Create `/var/ipcamfs` directory.

- Add to `/etc/fstab`:
  ```
  tmpfs /var/ipcamfs tmpfs mode=1755,uid=1000,gid=1000,size=350M 0 0
  ```

  You may want to adjust tmpfs size.

- Run `mount /var/ipcamfs`.

- Copy systemd unit file:
  ```
  cp /home/user/homekit/systemd/ipcam_rtsp2hls@.service /etc/systemd/system
  ```

- Create configuration directory:
  ```
  mkdir /etc/ipcam_rtsp2hls.conf.d
  ```

- Then for each `camname`:
  - create `/etc/ipcam_rtsp2hls.conf.d/camname.conf` with following content:
    ```
    USER=suer
    PASSWORD=password
    IP=192.168.1.2
    PORT=554
    # uncomment if needed
    # ARGS="--force-tcp"
    ```
  - run `systemctl enable ipcam_rtsp2hls@camname` and `systemctl start ipcam_rtsp2hls@camname`

## Recording

- Copy systemd unit file:

  ```
  cp /home/user/homekit/systemd/ipcam_capture@.service /etc/systemd/system
  ```

- Create configuration directory:
  ```
  mkdir /etc/ipcam_capture.conf.d
  ```

- Then for each `camname`:
  - create `/etc/ipcam_capture.conf.d/camname.conf` with following content:
    ```
    IP=192.168.1.2
    PORT=554
    CREDS="user:password"
    OUTDIR=/path/to/files
    # uncomment if needed
    # ARGS="--force-tcp"
    ```
  - run `systemctl enable ipcam_capture@camname` and `systemctl start ipcam_capture@camname`
