import pulumi as p
import pulumi_cloudflare as cloudflare

from ingress.cloudflared import create_cloudflared
from ingress.config import ComponentConfig
from utils.k8s import get_k8s_provider

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=component_config.cloudflare.api_key.value,
    email=component_config.cloudflare.email,
)

k8s_provider = get_k8s_provider()

create_cloudflared(component_config, k8s_provider, cloudflare_provider)
