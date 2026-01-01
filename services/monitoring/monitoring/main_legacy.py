"""A Python Pulumi program"""

import pulumi as p
import pulumi_docker as docker
import utils.cloudflare
import utils.docker

from monitoring.alloy_legacy import create_alloy_legacy
from monitoring.cadvisor_legacy import create_cadvisor_legacy
from monitoring.config import ComponentConfig
from monitoring.mimir_legacy import create_mimir_legacy


def main_legacy():
    component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

    stack = p.get_stack()
    org = p.get_organization()
    minio_stack_ref = p.StackReference(f'{org}/s3/{stack}')

    assert component_config.target
    docker_provider = utils.docker.get_provider(component_config.target)

    docker_opts = p.ResourceOptions(provider=docker_provider)

    assert component_config.cloudflare
    cloudflare_provider = utils.cloudflare.get_provider(component_config.cloudflare)

    # Create networks so we don't have to expose all ports on the host
    network = docker.Network('monitoring', opts=docker_opts)

    # Create node-exporter container
    create_cadvisor_legacy(component_config, network, docker_opts)
    create_alloy_legacy(component_config, network, cloudflare_provider, docker_opts)
    create_mimir_legacy(
        component_config, network, cloudflare_provider, minio_stack_ref, docker_opts
    )
