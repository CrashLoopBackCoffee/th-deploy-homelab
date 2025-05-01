"""
Create a Cloudflare tunnel for CouchDB
"""

import base64

import pulumi as p
import pulumi_cloudflare
import pulumi_docker as docker
import pulumi_random

from obsidian.config import ComponentConfig

import utils.cloudflare


def create_cloudflare_tunnel(
    component_config: ComponentConfig, network: docker.Network, opts: p.ResourceOptions
):
    """
    Create a Cloudflare tunnel for CouchDB
    """
    public_hostname = f'obsidian.{component_config.cloudflare.zone}'

    cloudflare_provider = pulumi_cloudflare.Provider(
        'cloudflare',
        api_key=component_config.cloudflare.api_key.value,
        email=component_config.cloudflare.email,
    )
    cloudflare_opts = p.ResourceOptions(provider=cloudflare_provider)
    cloudflare_invoke_opts = p.InvokeOptions(provider=cloudflare_provider)

    cloudflare_accounts = pulumi_cloudflare.get_accounts_output(opts=cloudflare_invoke_opts)
    cloudflare_account_id = cloudflare_accounts.results.apply(lambda results: results[0].id)

    password = pulumi_random.RandomPassword('tunnel', length=64)

    # First create a cloudflare tunnel
    tunnel = pulumi_cloudflare.ZeroTrustTunnelCloudflared(
        'couchdb',
        account_id=cloudflare_account_id,
        name='obsidian-couchdb',
        tunnel_secret=password.result.apply(
            lambda p: base64.b64encode(p.encode('utf-8')).decode('utf-8')
        ),
        config_src='cloudflare',
        opts=cloudflare_opts,
    )
    tunnel_token = pulumi_cloudflare.get_zero_trust_tunnel_cloudflared_token_output(
        account_id=cloudflare_account_id, tunnel_id=tunnel.id, opts=cloudflare_invoke_opts
    )

    zone = utils.cloudflare.get_zone('.'.join(public_hostname.split('.')[1:]), cloudflare_provider)

    record = pulumi_cloudflare.DnsRecord(
        'couchdb',
        proxied=True,
        name=public_hostname.split('.')[0],
        type='CNAME',
        content=tunnel.id.apply(lambda _id: f'{_id}.cfargotunnel.com'),
        ttl=1,
        zone_id=zone.zone_id,
        opts=cloudflare_opts,
    )

    public_hostname = p.Output.format('{}.{}', record.name, zone.name)

    pulumi_cloudflare.ZeroTrustTunnelCloudflaredConfig(
        'couchdb',
        account_id=cloudflare_account_id,
        tunnel_id=tunnel.id,
        config={
            'ingresses': [
                {
                    'service': 'http://obsidian-couchdb:5984',
                    'hostname': public_hostname,
                },
                {
                    'service': 'http_status:404',
                },
            ],
        },
        opts=cloudflare_opts,
    )

    image = docker.RemoteImage(
        'cloudflared',
        name=f'cloudflare/cloudflared:{component_config.cloudflared.version}',
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        'obsidian-cloudflared',
        name='cloudflared',
        image=image.image_id,
        command=[
            'tunnel',
            '--no-autoupdate',
            'run',
            '--token',
            tunnel_token.token,
        ],
        networks_advanced=[
            docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=['cloudflared']),
        ],
        restart='always',
        start=True,
        opts=opts,
    )
