"""A Python Pulumi program"""

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_docker as docker

from monitoring.alloy_legacy import create_alloy
from monitoring.cadvisor_legacy import create_cadvisor
from monitoring.config import ComponentConfig
from monitoring.mimir_legacy import create_mimir


def main_legacy():
    component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

    stack = p.get_stack()
    org = p.get_organization()
    minio_stack_ref = p.StackReference(f'{org}/s3/{stack}')

    provider = docker.Provider('synology', host='ssh://synology')

    opts = p.ResourceOptions(provider=provider)

    assert component_config.cloudflare
    cloudflare_provider = cloudflare.Provider(
        'cloudflare',
        api_key=str(component_config.cloudflare.api_key),
        email=component_config.cloudflare.email,
    )

    # Create networks so we don't have to expose all ports on the host
    network = docker.Network('monitoring', opts=opts)

    # Create node-exporter container
    create_cadvisor(network, opts)
    create_alloy(component_config, network, cloudflare_provider, opts)
    create_mimir(component_config, network, cloudflare_provider, minio_stack_ref, opts)
