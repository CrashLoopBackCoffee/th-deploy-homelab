"""
Deploys cadvisor to the target host.
"""

import pulumi as p
import pulumi_docker as docker

from monitoring.config import ComponentConfig


def create_cadvisor(
    component_config: ComponentConfig, network: docker.Network, opts: p.ResourceOptions
):
    """
    Deploys cadvisor to the target host.
    """
    assert component_config.cadvisor
    image = docker.RemoteImage(
        'cadvisor',
        name=f'ghcr.io/google/cadvisor:v{component_config.cadvisor.version}',
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        'cadvisor',
        image=image.image_id,
        name='cadvisor',
        command=['--disable_metrics=percpu', '--housekeeping_interval=10s', '--docker_only=true'],
        ports=[
            docker.ContainerPortArgs(internal=8080, external=8081),
        ],
        volumes=[
            docker.ContainerVolumeArgs(
                host_path=host_path, container_path=container_path, read_only=read_only
            )
            for host_path, container_path, read_only in [
                ('/', '/rootfs', True),
                ('/var/run', '/var/run', False),
                ('/sys', '/sys', True),
                ('/var/lib/docker', '/var/lib/docker', False),
            ]
        ],
        networks_advanced=[
            docker.ContainerNetworksAdvancedArgs(name=network.name, aliases=['cadvisor'])
        ],
        restart='always',
        start=True,
        opts=opts,
    )
