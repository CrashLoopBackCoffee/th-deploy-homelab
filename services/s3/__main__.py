"""A Python Pulumi program"""

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_docker as docker

from s3.config import ComponentConfig
from s3.minio import create_minio

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

provider = docker.Provider('synology', host='ssh://synology')

opts = p.ResourceOptions(provider=provider)

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=str(component_config.cloudflare.api_key),
    email=component_config.cloudflare.email,
)

# Create networks so we don't have to expose all ports on the host
network = docker.Network('s3', opts=opts)

create_minio(component_config, network, cloudflare_provider, opts)
