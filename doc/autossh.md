`/etc/systemd/system/my-ssh-tunnel.service`:

```
[Unit]
Description=ssh tunnel for localhost:22
After=network.target
StartLimitIntervalSec=0

[Service]
User=user
Group=user
Restart=on-failure
RestartSec=15
ExecStart=autossh -M 20001 -N -R 127.0.0.1:44223:127.0.0.1:22 -o StrictHostKeyChecking=no -o ExitOnForwardFailure=yes solarmon-tunnel@solarmon.ru
WorkingDirectory=/home/user

[Install]
WantedBy=multi-user.target
```