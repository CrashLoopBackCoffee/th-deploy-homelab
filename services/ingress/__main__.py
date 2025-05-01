import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s

from ingress.cloudflared import create_cloudflared
from ingress.config import ComponentConfig

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=component_config.cloudflare.api_key.value,
    email=component_config.cloudflare.email,
)

stack = p.get_stack()
org = p.get_organization()
k8s_stack_ref = p.StackReference(f'{org}/kubernetes/{stack}')

k8s_provider = k8s.Provider('k8s', kubeconfig=k8s_stack_ref.get_output('kubeconfig'))

create_cloudflared(component_config, k8s_provider, cloudflare_provider)
