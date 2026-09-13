"""Generate MO2 executable settings; credentials are not printed or stored by this tool."""
import argparse
import json
import re


def settings(role, address='127.0.0.1', port=1237, client_port=1240, nickname='Stalker', players=128):
    if role not in ('server', 'client'):
        raise ValueError('Invalid role')
    if not (1024 <= port <= 65535 and 1024 <= client_port <= 65535 and port != client_port):
        raise ValueError('Ports must be distinct and within 1024..65535')
    if not 1 <= players <= 128:
        raise ValueError('players must be 1..128')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', nickname):
        raise ValueError('Use a nickname with 1..32 letters, digits, dot, underscore or hyphen')
    if not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', address):
        raise ValueError('Use an IPv4 address or DNS hostname without URL/command delimiters')
    address = 'localhost' if address == '127.0.0.1' else address
    # Isolated appdata is configured in a copied fsgame.ltx per process (see README).
    args = f'-netcoop -noprefetch -logname gamma_{role}_{nickname} -ltx gamma_{role}.ltx '
    if role == 'server':
        args += f'-netport {port} -start server(all/single/alife/new/portsv={port}/maxplayers={players}) '
        args += f'client(localhost/name={nickname}/port={port}/portcl={client_port})'
    else:
        args += f'-start client({address}/name={nickname}/port={port}/portcl={client_port})'
    return {'title': 'GAMMA NetAnomaly - ' + role, 'binary': 'bin/AnomalyGammaNetDX11.exe',
            'arguments': args, 'profile': 'GAMMA NetAnomaly - ' + role,
            'working_directory': '<Anomaly game directory>',
            'notes': 'Server uses a rendered ALife host until headless GAMMA callbacks pass acceptance.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--role', choices=['client', 'server'], required=True)
    p.add_argument('--address', default='127.0.0.1')
    p.add_argument('--port', type=int, default=1237)
    p.add_argument('--client-port', type=int, default=1240)
    p.add_argument('--nickname', default='Stalker')
    p.add_argument('--players', type=int, default=128)
    print(json.dumps(settings(**vars(p.parse_args())), indent=2))
