import json

import pulumi as p
import pulumi_cloudflare as cloudflare
import utils.opnsense.unbound.host_override
import yaml

from unifi.config import ComponentConfig


def _get_cloud_config(hostname: str, username: str, ssh_public_key: str) -> str:
    PACKAGES = ' '.join(
        [
            'apt-transport-https',
            'ca-certificates',
            'curl',
            'gpg',
            'net-tools',
            'vim',
        ]
    )
    return '#cloud-config\n' + yaml.safe_dump(
        {
            # User config
            'users': [
                'default',
                {
                    'name': username,
                    'groups': ['sudo'],
                    'shell': '/bin/bash',
                    'ssh_authorized_keys': [ssh_public_key],
                    'lock_passwd': True,
                    'sudo': ['ALL=(ALL) NOPASSWD:ALL'],
                },
            ],
            # Install packages and configure MicroK8s
            'runcmd': [
                # System update and prep
                f'hostnamectl set-hostname {hostname}',
                'apt-get update -y',
                'apt-get upgrade -y',
                f'DEBIAN_FRONTEND=noninteractive apt-get install -y {PACKAGES}',
                # Install docker
                'apt-get install -y docker.io',
                f'usermod -a -G docker {username}',
                # Start guest agent to keep Pulumi waiting until all of the above is ready
                'DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent',
                'systemctl enable qemu-guest-agent',
                'systemctl start qemu-guest-agent',
                'echo "done" /tmp/cloud-config.done',
            ],
        }
    )


def create_unifi(
    component_config: ComponentConfig,
    cloudflare_provider: cloudflare.Provider,
) -> None:

    # Create local DNS record
    utils.opnsense.unbound.host_override.HostOverride(
        'unifi',
        host=component_config.unifi.hostname.split('.', 1)[0],
        domain=component_config.unifi.hostname.split('.', 1)[1],
        record_type='A',
        ipaddress=str(component_config.unifi.address),
    )

    # Create scoped Cloudflare API token for acme.sh DNS-01 challenge
    acme_token = cloudflare.ApiToken(
        'cloudflare-acme-token',
        name=f'unifi-{p.get_stack()}-acme',
        policies=[
            {
                'effect': 'allow',
                'permission_groups': [
                    # Zone Read
                    {'id': 'c8fed203ed3043cba015a93ad1616f1f'},
                    # DNS Write
                    {'id': '4755a26eedb94da69e1066d98aa820be'},
                ],
                'resources': json.dumps({'com.cloudflare.api.account.zone.*': '*'}),
            },
        ],
        opts=p.ResourceOptions(provider=cloudflare_provider),
    )

    p.export('unifi_address', str(component_config.unifi.address))
    p.export('unifi_hostname', component_config.unifi.hostname)
    p.export('unifi_ssh_user', component_config.unifi.ssh_user)
    p.export('cloudflare_acme_token', p.Output.secret(acme_token.value))
