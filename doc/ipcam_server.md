# ipcam_server.py

## Configuration

Config example (`yaml`)

```
server:
  listen: 0.0.0.0:8320

camera:
  1:
    recordings_path: "/data1/cam-1"
    motion_path: "/data1/cam-1/motion"
  2:
    recordings_path: "/data2/cam-2"
    motion_path: "/data2/cam-2/motion"
  3:
    recordings_path: "/data3/cam-3"
    motion_path: "/data3/cam-3/motion"

motion:
  padding: 2
  telegram: true

logging:
  verbose: true

telegram:
  token: ""
  chat_id: ""
  parse_mode: HTML
```

## Usage

Use provided systemd unit file.