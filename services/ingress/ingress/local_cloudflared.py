import base64

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_random
import utils.cloudflare

from ingress.config import ComponentConfig


def create_local_cloudflared(
    component_config: ComponentConfig,
    cloudflare_provider: cloudflare.Provider,
):
    if not component_config.local_cloudflared:
        return

    cloudflare_opts = p.ResourceOptions(provider=cloudflare_provider)
    cloudflare_invoke_opts = p.InvokeOptions(provider=cloudflare_provider)

    cloudflare_accounts = cloudflare.get_accounts_output(opts=cloudflare_invoke_opts)
    cloudflare_account_id = cloudflare_accounts.results.apply(lambda results: results[0].id)
    tunnel_password = pulumi_random.RandomPassword('local-cloudflared', length=64)
    tunnel = cloudflare.ZeroTrustTunnelCloudflared(
        'local-cloudflared-tunnel',
        account_id=cloudflare_account_id,
        name='cloudflared-local-dev',
        tunnel_secret=tunnel_password.result.apply(
            lambda password: base64.b64encode(password.encode()).decode()
        ),
        config_src='cloudflare',
        opts=cloudflare_opts,
    )

    tunnel_token = cloudflare.get_zero_trust_tunnel_cloudflared_token_output(
        account_id=cloudflare_account_id,
        tunnel_id=tunnel.id,
        opts=cloudflare_invoke_opts,
    )

    ingress_rules = []
    for ingress in component_config.local_cloudflared:
        rule: cloudflare.ZeroTrustTunnelCloudflaredConfigConfigIngressArgsDict = {
            'service': ingress.service,
            'hostname': ingress.hostname,
        }
        if ingress.set_origin_server_name:
            rule['origin_request'] = {'origin_server_name': ingress.hostname}
        ingress_rules.append(rule)

    cloudflare.ZeroTrustTunnelCloudflaredConfig(
        'local-cloudflared',
        account_id=cloudflare_account_id,
        tunnel_id=tunnel.id,
        config={
            'ingresses': [
                *ingress_rules,
                {'service': 'http_status:404'},
            ],
        },
        opts=cloudflare_opts,
    )

    zone = utils.cloudflare.get_zone(component_config.cloudflare.zone, cloudflare_provider)
    for ingress in component_config.local_cloudflared:
        hostname_prefix = ingress.hostname.split('.')[0]
        cloudflare.DnsRecord(
            f'local-{ingress.hostname}',
            proxied=True,
            name=hostname_prefix,
            type='CNAME',
            content=p.Output.format('{}.cfargotunnel.com', tunnel.id),
            ttl=1,
            zone_id=zone.zone_id,
            opts=cloudflare_opts,
        )

    local_tunnel_token = p.Output.secret(tunnel_token.token)
    p.export('local_cloudflared_tunnel_name', tunnel.name)
    p.export('local_cloudflared_tunnel_id', tunnel.id)
    p.export('local_cloudflared_tunnel_token', local_tunnel_token)
    p.export(
        'local_cloudflared_run_command',
        p.Output.format('cloudflared tunnel --no-autoupdate run --token {}', local_tunnel_token),
    )
    p.export(
        'local_cloudflared_ingress_hostnames',
        [ingress.hostname for ingress in component_config.local_cloudflared],
    )
