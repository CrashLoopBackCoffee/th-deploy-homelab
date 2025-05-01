import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_proxmoxve as proxmoxve

from kubernetes.config import ComponentConfig
from kubernetes.microk8s import create_microk8s

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

create_microk8s(component_config, cloudflare_provider, proxmox_provider)
