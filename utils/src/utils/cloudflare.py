import functools

import pulumi as p
import pulumi_cloudflare as cloudflare


@functools.cache
def get_cloudflare_zone():
    return p.Config().require_object('cloudflare')['zone']


def get_cloudflare_provider() -> cloudflare.Provider:
    pulumi_config = p.Config()

    # Load cloudflare config from ESC
    cloudflare_pulumi_config = pulumi_config.require_object('cloudflare')
    api_key = cloudflare_pulumi_config['api-key']
    email = cloudflare_pulumi_config['email']

    return cloudflare.Provider(
        'cloudflare',
        api_key=api_key,
        email=email,
    )


def get_zone(
    name: str, cloudflare_provider: cloudflare.Provider
) -> p.Output[cloudflare.GetZoneResult]:
    return cloudflare.get_zone_output(
        filter={'match': 'all', 'name': name},
        opts=p.InvokeOptions(provider=cloudflare_provider),
    )


def create_cloudflare_cname(
    name: str,
    zone_name: str,
    cloudflare_provider: cloudflare.Provider,
    opts: p.ResourceOptions | None = None,
) -> cloudflare.DnsRecord:
    cloudflare_opts = p.ResourceOptions(provider=cloudflare_provider)
    if opts:
        cloudflare_opts = opts.merge(cloudflare_opts)

    zone = cloudflare.get_zone_output(
        filter={'match': 'all', 'name': zone_name},
        opts=p.InvokeOptions(provider=cloudflare_provider),
    )

    return cloudflare.DnsRecord(
        name,
        proxied=False,
        name=name,
        type='CNAME',
        content=f'home.{zone_name}',
        ttl=60,
        zone_id=zone.zone_id,
        opts=cloudflare_opts,
    )
