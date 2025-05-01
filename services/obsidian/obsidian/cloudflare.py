"""
Create a Cloudflare tunnel for CouchDB
"""

import base64

import pulumi
import pulumi_cloudflare
import pulumi_docker as docker
import pulumi_random
from pulumi import InvokeOptions, ResourceOptions

from obsidian.utils import get_image


def create_cloudflare_tunnel(network: docker.Network, opts: ResourceOptions):
    """
    Create a Cloudflare tunnel for CouchDB
    """
    config = pulumi.Config()

    public_hostname = config.require("public-hostname")

    cloudflare_provider = pulumi_cloudflare.Provider(
        "cloudflare",
        api_key=config.require("cloudflare-api-key"),
        email=config.require("cloudflare-email"),
    )
    cloudflare_opts = ResourceOptions(provider=cloudflare_provider)
    accounts = pulumi_cloudflare.get_accounts(
        opts=InvokeOptions(provider=cloudflare_provider)
    )
    account_id = accounts.accounts[0]["id"]

    password = pulumi_random.RandomPassword("tunnel", length=64)

    # First create a cloudflare tunnel
    tunnel = pulumi_cloudflare.Tunnel(
        "couchdb",
        account_id=account_id,
        name="obsidian-couchdb",
        secret=password.result.apply(
            lambda p: base64.b64encode(p.encode("utf-8")).decode("utf-8")
        ),
        config_src="cloudflare",
        opts=cloudflare_opts,
    )

    zone = pulumi_cloudflare.get_zone(
        account_id=account_id,
        name=".".join(public_hostname.split(".")[1:]),
        opts=InvokeOptions(provider=cloudflare_provider),
    )

    record = pulumi_cloudflare.Record(
        "couchdb",
        proxied=True,
        name=public_hostname.split(".")[0],
        type="CNAME",
        value=tunnel.id.apply(lambda _id: f"{_id}.cfargotunnel.com"),
        zone_id=zone.id,
        opts=cloudflare_opts,
    )

    pulumi_cloudflare.TunnelConfig(
        "couchdb",
        account_id=account_id,
        tunnel_id=tunnel.id,
        config=pulumi_cloudflare.TunnelConfigConfigArgs(
            ingress_rules=[
                pulumi_cloudflare.TunnelConfigConfigIngressRuleArgs(
                    service="http://obsidian-couchdb:5984",
                    hostname=record.hostname,
                ),
                pulumi_cloudflare.TunnelConfigConfigIngressRuleArgs(
                    service="http_status:404",
                ),
            ],
        ),
        opts=cloudflare_opts,
    )

    image = docker.RemoteImage(
        "cloudflared",
        name=get_image("cloudflared"),
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        "obsidian-cloudflared",
        name="cloudflared",
        image=image.image_id,
        command=[
            "tunnel",
            "--no-autoupdate",
            "run",
            "--token",
            tunnel.tunnel_token,
        ],
        networks_advanced=[
            docker.ContainerNetworksAdvancedArgs(
                name=network.name, aliases=["cloudflared"]
            ),
        ],
        restart="always",
        start=True,
        opts=opts,
    )
