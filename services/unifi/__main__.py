import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_proxmoxve as proxmoxve

from unifi.acme import create_certificate
from unifi.config import ComponentConfig
from unifi.unifi import create_unifi

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

token_output = component_config.proxmox.api_token.value

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=component_config.cloudflare.api_key.value,
    email=component_config.cloudflare.email,
)

proxmox_provider = proxmoxve.Provider(
    'proxmox',
    endpoint=component_config.proxmox.api_endpoint,
    api_token=token_output,
    insecure=component_config.proxmox.insecure,
    ssh={
        'username': 'root',
        'agent': True,
    },
)

# Create TLS certs
certificate = create_certificate(component_config)

# Create the Unifi VM
create_unifi(component_config, certificate, proxmox_provider)
