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
            bind_port = 55000 + config[host]['bind_slot']*10 + i
            target = ('127.0.0.1' if host == tun_host else network_prefix + '.' + str(config[tun_host]['ipv4'])) + ':' + str(config[tun_host]['http_port'])
            buf.append(f'-R 127.0.0.1:{bind_port}:{target}')
            i += 1

        print(host)
        print(' '.join(buf))
        print()
