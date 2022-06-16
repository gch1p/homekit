## Dependencies

[**pyssim**](https://github.com/jterrace/pyssim), which can be installed from pypi:
```
pip3 install pyssim
```

## Configuration

```
esp32cam_web_addr = "192.168.1.2:80"

[pyssim]
bin = "/home/user/.local/bin/pyssim"
width = 250
height = 375
threshold = 0.88

[node]
name = "sensor_node_name"
interval = 15
server_addr = "127.0.0.1:8311"

[logging]
verbose = true
```

To enable Telegram notifications when **pyssim** returned `score` is less then `threshold`,
add following section to the config:

```
[telegram]
chat_id = "..."
token = "..."
```