import pulumi as p
import pulumi_cloudflare as cloudflare


def _get_cloudflare_account_id(cloudflare_provider: cloudflare.Provider) -> p.Output[str]:
    """
    Returns the Cloudflare account ID.
    """
    accounts = cloudflare.get_accounts_output(opts=p.InvokeOptions(provider=cloudflare_provider))
    return accounts.accounts.apply(lambda accounts: accounts[0]['id'])


def create_cloudflare_cname(
    name: str, zone_name: str, cloudflare_provider: cloudflare.Provider
) -> cloudflare.Record:
    account_id = _get_cloudflare_account_id(cloudflare_provider)
    zone = cloudflare.get_zone_output(
        account_id=account_id,
        name=zone_name,
        opts=p.InvokeOptions(provider=cloudflare_provider),
    )

    return cloudflare.Record(
        name,
        proxied=False,
        name=name,
        type='CNAME',
        content=f'home.{zone_name}',
        zone_id=zone.id,
        opts=p.ResourceOptions(provider=cloudflare_provider),
    )
