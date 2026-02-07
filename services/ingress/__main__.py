import pulumi as p
import pulumi_cloudflare as cloudflare

from ingress.acme import AcmeSynology
from ingress.cloudflared import create_cloudflared
from ingress.config import ComponentConfig
from ingress.local_cloudflared import create_local_cloudflared
from utils.k8s import get_k8s_provider

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=component_config.cloudflare.api_key.value,
    email=component_config.cloudflare.email,
)

k8s_provider = get_k8s_provider()


create_cloudflared(component_config, k8s_provider, cloudflare_provider)
create_local_cloudflared(component_config, cloudflare_provider)

AcmeSynology('default', component_config, k8s_provider)
