# sound_bot

## Configuration example

```toml
[bot]
token = "..."
users = [1, 2]
manual_record_allowlist = [ 1 ]
notify_users = [ 1, 2 ]

record_intervals = [15, 30, 60, 180, 300, 600]
guard_server = "1.2.3.4:8311"

[api]
token = "..."
host = "..."

[nodes]
name1.addr = '1.2.3.4:8313'
name1.label = { ru="название 1", en="name 1" }

name2.addr = '1.2.3.5:8313'
name2.label = { ru="название2", en="name 2" }

[sound_sensors]
name1 = { ru="название 1", en="name 1" }
name2 = { ru="название 2", en="name 2" }

[cameras]
name1 = { ru="название 1", en="name 1", type="esp32", addr="1.2.3.4:80", settings = {framesize=9, vflip=true, hmirror=true, lenc=true, wpc=true, bpc=false, raw_gma=false, agc=true, gainceiling=5, quality=10, awb_gain=false, awb=true, aec_dsp=true, aec=true} }

[logging]
verbose = false
default_fmt = true
```