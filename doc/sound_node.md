# Sound Node

## Requirements

```
apt install -y python3-aiohttp python3-requests python3-toml
```

## Configuration

Orange Pi Lite config (`/etc/sound_node.toml`):

```toml
[node]
listen = "0.0.0.0:8313"
process_wait_timeout = 10
name = "nodename"

record_max_time = 1800
storage = "/var/recordings"

[arecord]
bin = "/usr/bin/arecord"

[lame]
bin = "/usr/bin/lame"
bitrate = 192

[amixer]
bin = "/usr/bin/amixer"
controls = [
        {
                name = "Line In",
                caps = ["mute", "cap", "volume"]
        },
        {
                name = "Mic1",
                caps = ["mute", "cap", "volume"]
        },
        {
                name = "Mic1 Boost",
                caps = ["volume"]
        }
]

[logging]
verbose = false
default_fmt = true
```

## Audio recording

Install `lame`.

Command to record audio: `arecord -v -f S16 -r 44100 -t raw 2>/dev/null | lame -r -s 44.1 -b 192 -m m - output.mp3 >/dev/null 2>/dev/null`

## Uploading audios to remote server

- Generate ssh keys for root on each sound node:
  ```
  cd /root/.ssh
  ssh-keygen -t ed25519
  ```
- Add public keys on the remote server
- Copy `tools/sync-recordings-to-remote.sh` script to `/usr/local/bin` on all sound nodes, don't forget to `chmod +x` it.
- Add following lines to the root crontab (on all sound nodes):
  ```
  TG_TOKEN="your telegram bot token"
  TG_CHAT_ID="your telegram chat id"
  
  30 * * * *  /usr/local/bin/sync-recordings-to-remote.sh
  ```