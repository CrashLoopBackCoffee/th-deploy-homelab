import pathlib

import pulumi as p
import pulumi_command
import pulumi_docker as docker

from monitoring.config import ComponentConfig
from monitoring.utils import get_assets_path


def directory_content(path: pathlib.Path) -> list[str]:
    """
    Hashes the contents of a directory.
    """
    contents = []
    for file in path.rglob('*'):
        if file.is_file():
            contents.append(file.read_text())
    return contents


def create_alloy(
    component_config: ComponentConfig,
    network: docker.Network,
    opts: p.ResourceOptions,
):
    """
    Deploys Alloy to the target host.
    """
    target_root_dir = component_config.target.root_dir
    target_host = component_config.target.host
    target_user = component_config.target.user

    alloy_path = get_assets_path() / 'alloy'

    # Create alloy-config folder
    alloy_config_dir_resource = pulumi_command.remote.Command(
        'create-alloy-config',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/alloy-config',
    )
    alloy_data_dir_resource = pulumi_command.remote.Command(
        'create-alloy-data',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/alloy-data',
    )

    sync_command = (
        f'rsync --rsync-path /bin/rsync -av --delete '
        f'{alloy_path}/ '
        f'{target_user}@{target_host}:{target_root_dir}/alloy-config/'
    )

    alloy_config = directory_content(alloy_path)
    alloy_config = pulumi_command.local.Command(
        'alloy-config',
        create=sync_command,
        triggers=[alloy_config, alloy_config_dir_resource.id],
    )

    image = docker.RemoteImage(
        'alloy',
        name=f'grafana/alloy:{component_config.alloy.version}',
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        'alloy',
        image=image.image_id,
        command=[
            'run',
            '--server.http.listen-addr=0.0.0.0:9091',
            '--storage.path=/var/lib/alloy/data',
            # Required for live debugging
            '--stability.level=experimental',
            '/etc/alloy/',
        ],
        envs=[
            f'GRAFANA_CLOUD_API_USER={component_config.alloy.username}',
            f'GRAFANA_CLOUD_API_TOKEN={component_config.alloy.token}',
        ],
        ports=[{'internal': 9091, 'external': 9091}],
        volumes=[
            {
                'host_path': f'{target_root_dir}/alloy-config',
                'container_path': '/etc/alloy',
            },
            {
                'host_path': f'{target_root_dir}/alloy-data',
                'container_path': '/var/lib/alloy/data',
            },
        ],
        networks_advanced=[{'name': network.name, 'aliases': ['alloy']}],
        restart='always',
        start=True,
        opts=p.ResourceOptions.merge(
            opts,
            p.ResourceOptions(depends_on=[alloy_config, alloy_data_dir_resource]),
        ),
    )
