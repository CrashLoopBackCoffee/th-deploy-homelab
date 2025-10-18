"""A Python Pulumi program"""

import pulumi as p
import pulumi_docker as docker
import utils.cloudflare
import utils.docker

from s3.config import ComponentConfig
from s3.minio import create_minio

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

docker_provider = utils.docker.get_provider(component_config.target)
docker_opts = p.ResourceOptions(provider=docker_provider)

cloudflare_provider = utils.cloudflare.get_provider(component_config.cloudflare)

# Create networks so we don't have to expose all ports on the host
network = docker.Network('s3', opts=docker_opts)

create_minio(component_config, network, cloudflare_provider, docker_opts)
