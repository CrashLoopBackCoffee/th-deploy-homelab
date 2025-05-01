"""A Python Pulumi program"""

import pulumi as p
import pulumi_docker

from obsidian.cloudflare import create_cloudflare_tunnel
from obsidian.config import ComponentConfig
from obsidian.couchdb import create_couchdb

component_config = ComponentConfig.model_validate(p.Config().require_object('config'))

target_host = component_config.target.host

provider = pulumi_docker.Provider('synology', host=f'ssh://{target_host}')

opts = p.ResourceOptions(provider=provider)

# Create networks so we don't have to expose all ports on the host
network = pulumi_docker.Network('obsidian', opts=opts)

create_couchdb(component_config, network, opts)
create_cloudflare_tunnel(component_config, network, opts)
