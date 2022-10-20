# Inverter Bot

### Bot configuration

**`~/.config/inverter_bot/config.toml`**:

```toml
[bot]
token = "..."
users = [ 1, 2, 3 ]
notify_users = [ 1, 2 ]

[inverter]
host = "127.0.0.1"
port = 8305

[ac_mode.generator]
thresholds = [51, 58]
initial_current = 2

[ac_mode.utilities]
thresholds = [48, 54]
initial_current = 40

[monitor]
vlow = 47
vcrit = 45

gen_currents = [2, 10, 20, 30]
gen_raise_intervals = [
    180, # 3 minutes for 2 A, then
    120, # 2 more minutes for 10 A, then
    120, # 3 more minutes for 20 A, then, finally, 30 A 
]
gen_cur30_v_limit = 56.9
gen_cur20_v_limit = 56.7
gen_cur10_v_limit = 54

gen_floating_v = 54
gen_floating_time_max = 7200

[logging]
verbose = false

[api]
token = "..."
```

### systemd integration

**`/etc/systemd/system/inverter_bot.service`**:

```systemd
[Unit]
Description=inverter bot
After=inverterd.service

[Service]
User=user
Group=user
Restart=on-failure
ExecStart=/home/user/home/bin/inverter_bot
WorkingDirectory=/home/user

[Install]
WantedBy=multi-user.target
```


### Commands
```
lang - Set language
status - Show status
config - Show configuration
errors - Show errors
flags - Toggle flags
calcw - Calculate daily watts usage 
calcwadv - Advanced watts usage calculator
setbatuv - Set battery under voltage
setgencc - Set AC charging current
setgenct - Set AC charging thresholds
setacmode - Set AC input mode
setosp - Set output source priority
monstatus - Monitor: dump state
monsetcur - Monitor: set charging currents
```