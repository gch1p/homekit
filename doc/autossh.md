`/etc/systemd/system/my-ssh-tunnel.service`:

```
[Unit]
Description=ssh tunnel
After=network.target
StartLimitIntervalSec=0

[Service]
User=user
Group=user
Restart=always
RestartSec=1
ExecStart=autossh -M 0 -NC -R 127.0.0.1:44223:127.0.0.1:22 -o StrictHostKeyChecking=no -o LogLevel=ERROR -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=2 user@host
WorkingDirectory=/home/user

[Install]
WantedBy=multi-user.target
```

On server:

```
ClientAliveInterval 15
ClientAliveCountMax 2
```