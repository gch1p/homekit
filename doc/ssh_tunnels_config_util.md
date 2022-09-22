## Config example

`~/.config/ssh_tunnels_config_util.toml`:

```toml
network = "192.168.1"
http_bind_base = 20000
ssh_bind_base = 21000

[nas1]
ipv4 = 100
http_port = 80
ssh_port = 22
bind_slot = 0

[nas2]
ipv4 = 101
http_port = 8080
ssh_port = 22
bind_slot = 1
```

## Usage

Write config, run the script and use the output in the ssh tunnel service.