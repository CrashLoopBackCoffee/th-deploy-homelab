#!/usr/bin/env python3
"""Dynamic Ansible inventory populated from the unifi Pulumi stack outputs."""

import argparse
import json
import subprocess
import sys

from pathlib import Path

STACK = 'prod'

# Path to the unifi Pulumi project (two levels up from this inventory file)
PULUMI_PROJECT_DIR = Path(__file__).parent.parent.parent


def get_stack_outputs() -> dict:
    result = subprocess.run(
        ['pulumi', 'stack', 'output', '--json', '--show-secrets', '--stack', STACK],
        cwd=PULUMI_PROJECT_DIR,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def build_inventory(outputs: dict) -> dict:
    host = outputs['unifi_address']
    return {
        '_meta': {
            'hostvars': {
                host: {
                    'ansible_user': outputs['unifi_ssh_user'],
                    'unifi_hostname': outputs['unifi_hostname'],
                    'cloudflare_token': outputs['cloudflare_acme_token'],
                },
            },
        },
        'unifi': {
            'hosts': [host],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--host')
    args = parser.parse_args()

    if args.list:
        outputs = get_stack_outputs()
        print(json.dumps(build_inventory(outputs), indent=2))
    elif args.host:
        outputs = get_stack_outputs()
        host = outputs['unifi_address']
        if args.host == host:
            inv = build_inventory(outputs)
            print(json.dumps(inv['_meta']['hostvars'][host], indent=2))
        else:
            print('{}')
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
