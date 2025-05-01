"""A Python Pulumi program"""

import pulumi as p
import pulumi_docker as docker

from s3.config import ComponentConfig
from s3.minio import create_minio

import utils.cloudflare

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

provider = docker.Provider('synology', host='ssh://synology')

opts = p.ResourceOptions(provider=provider)

cloudflare_provider = utils.cloudflare.get_provider(component_config.cloudflare)

# Create networks so we don't have to expose all ports on the host
network = docker.Network('s3', opts=opts)

create_minio(component_config, network, cloudflare_provider, opts)
