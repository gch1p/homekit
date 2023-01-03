## config example

```
[mqtt]
host = "mqtt.solarmon.ru"
port = 8883

client_id = "relay_mqtt_util"
username = ""
password = ""

[relay]
devices = ['id1', 'id2']

[server]
listen = "0.0.0.0:8821"

[logging]
verbose = false
```