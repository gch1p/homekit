
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

storages:
  - mountpoint: "/data1"
    cams: [1]
  - mountpoint: "/data2"
    cams: [2]
  - mountpoint: "/data3"
    cams: [3]

motion:
  padding: 2
  telegram: true

logging:
  verbose: true

telegram:
  token: ""
  chat_id: ""
  parse_mode: HTML

  fragment_url_templates:
    - ["example", "https://example.ru/cam-{camera}/motion/{file}"]

  original_file_url_templates:
    - ["example", "https://example.ru/cam-{camera}/{file}"]

fix_interval: 600
fix_enabled: true

cleanup_min_gb: 200
cleanup_interval: 86400

```

## Usage

Use provided systemd unit file.