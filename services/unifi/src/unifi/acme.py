import pulumi as p
import pulumi_tls as tls
import pulumiverse_acme as acme

from unifi.config import ComponentConfig


def create_certificate(
    component_config: ComponentConfig,
) -> acme.Certificate:
    # Create the certificate
    acme_provider = acme.Provider(
        'acme-prod',
        server_url='https://acme-v02.api.letsencrypt.org/directory',
    )
    acme_opts = p.ResourceOptions(provider=acme_provider)

    private_key = tls.PrivateKey('unifi', algorithm='RSA')

    reg = acme.Registration(
        'unifi',
        account_key_pem=private_key.private_key_pem,
        email_address=component_config.cloudflare.email,
        opts=acme_opts,
    )

    return acme.Certificate(
        'unifi',
        account_key_pem=reg.account_key_pem,
        common_name=component_config.unifi.hostname,
        dns_challenges=[
            {
                'provider': 'cloudflare',
                'config': {
                    'CF_API_EMAIL': component_config.cloudflare.email,
                    'CF_API_KEY': component_config.cloudflare.api_key.value,
                },
            }
        ],
        opts=acme_opts,
    )
