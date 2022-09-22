#!/usr/bin/env python3

from home.config import config

if __name__ == '__main__':
    config.load('ssh_tunnels_config_util')

    network_prefix = config['network']
    hostnames = []

    for k, v in config.items():
        if type(v) is not dict:
            continue
        hostnames.append(k)

    for host in hostnames:
        buf = []
        i = 0
        for tun_host in hostnames:
            http_bind_port = config['http_bind_base'] + config[host]['bind_slot'] * 10 + i
            ssh_bind_port = config['ssh_bind_base'] + config[host]['bind_slot'] * 10 + i

            if tun_host == host:
                target_host = '127.0.0.1'
            else:
                target_host = f'{network_prefix}.{config[tun_host]["ipv4"]}'

            buf.append(f'-R 127.0.0.1:{http_bind_port}:{target_host}:{config[tun_host]["http_port"]}')
            buf.append(f'-R 127.0.0.1:{ssh_bind_port}:{target_host}:22')

            i += 1

        print(host)
        print(' '.join(buf))
        print()
