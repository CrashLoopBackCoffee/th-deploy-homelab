import pulumi as p

from unifi.config import ComponentConfig
from unifi.unifi import create_unifi
from utils.cloudflare import get_cloudflare_provider

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = get_cloudflare_provider()


# Create the Unifi VM
create_unifi(component_config, cloudflare_provider)
