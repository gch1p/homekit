## Configuration

```
[server]
listen = "0.0.0.0:8311"
guard_control = true                    
guard_recording_default = false  

[sensor_to_sound_nodes_relations]
big_house = ['bh1', 'bh2']
john = ['john']

[sensor_to_camera_nodes_relations]
big_house = ['bh']
john = ['john']

[sound_nodes]
bh1 = { addr = '192.168.1.2:8313', durations = [7, 30] }
bh2 = { addr = '192.168.1.3:8313', durations = [10, 60] }
john = { addr = '192.168.1.4:8313', durations = [10, 60] }

[camera_nodes]
bh = { addr = '192.168.1.2:8314', durations = [7, 30] }
john = { addr = '192.168.1.4:8314', durations = [10, 60] }

[api]
token = "..."
host = "..."

[logging]
verbose = false
default_fmt = true
```