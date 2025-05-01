import pulumi as p
import pulumi_cloudflare as cloudflare

from proxmox.config import ComponentConfig

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=str(component_config.cloudflare.api_key),
    email=component_config.cloudflare.email,
)
