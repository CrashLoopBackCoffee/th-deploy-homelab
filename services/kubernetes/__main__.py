import pulumi as p

from kubernetes.config import ComponentConfig
from kubernetes.microk8s import create_microk8s
from utils.cloudflare import get_cloudflare_provider
from utils.proxmox import get_proxmox_provider

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = get_cloudflare_provider()

proxmox_provider = get_proxmox_provider()

create_microk8s(component_config, cloudflare_provider, proxmox_provider)
