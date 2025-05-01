import pulumi as p
import pulumi_cloudflare as cloudflare

from utils.model import CloudflareConfig


def get_provider(config: CloudflareConfig) -> cloudflare.Provider:
    return cloudflare.Provider(
        'cloudflare',
        api_key=config.api_key.value,
        email=config.email,
    )


def get_zone(
    name: str, cloudflare_provider: cloudflare.Provider
) -> p.Output[cloudflare.GetZoneResult]:
    return cloudflare.get_zone_output(
        filter={'match': 'all', 'name': name},
        opts=p.InvokeOptions(provider=cloudflare_provider),
    )


def create_cloudflare_cname(
    name: str, zone_name: str, cloudflare_provider: cloudflare.Provider
) -> cloudflare.DnsRecord:
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
        opts=p.ResourceOptions(provider=cloudflare_provider),
    )
