# Sensors Bot

Configuration is stored in **`~/.config/sensors_bot/config.toml`**.

Example:

```toml
[bot]
token = "..."
users = [
        1,  # user 1
        2,  # user 2
        3,  # user 3 
]

[api]
token = ..."

[sensors.name1]
ip = "192.168.0.2"
port = 8306
label_ru = "Тут"
label_en = "Here"

[sensors.name2]
ip = "192.168.0.3"
port = 8307
label_ru = "Там"
label_en = "There"

[logging]
verbose = false
```

## Dependencies

```
apt install python3-matplotlib
```