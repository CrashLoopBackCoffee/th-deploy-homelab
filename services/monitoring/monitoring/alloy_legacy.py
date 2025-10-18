import urllib.error
import urllib.request

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_command
import pulumi_docker as docker
import utils.cloudflare
import utils.utils

from monitoring.config import ComponentConfig
from monitoring.utils import get_assets_path


def create_alloy(
    component_config: ComponentConfig,
    network: docker.Network,
    cloudflare_provider: cloudflare.Provider,
    opts: p.ResourceOptions,
):
    """
    Deploys Alloy to the target host.
    """
    assert component_config.target
    assert component_config.cloudflare
    assert component_config.alloy_legacy
    target_root_dir = component_config.target.root_dir
    target_host = component_config.target.host
    target_user = component_config.target.user

    alloy_path = get_assets_path() / 'alloy_legacy'

    # Create alloy DNS record
    dns_record = utils.cloudflare.create_cloudflare_cname(
        'alloy-legacy', component_config.cloudflare.zone, cloudflare_provider
    )

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

    alloy_config = utils.utils.directory_content(alloy_path)
    alloy_config = pulumi_command.local.Command(
        'alloy-config',
        create=sync_command,
        triggers=[alloy_config, alloy_config_dir_resource.id],
    )

    image = docker.RemoteImage(
        'alloy',
        name=f'grafana/alloy:{component_config.alloy_legacy.version}',
        keep_locally=True,
        opts=opts,
    )

    container = docker.Container(
        'alloy',
        image=image.image_id,
        name='alloy',
        command=[
            'run',
            '--server.http.listen-addr=0.0.0.0:9091',
            '--storage.path=/var/lib/alloy/data',
            '--disable-reporting',
            # Required for live debugging
            '--stability.level=experimental',
            '/etc/alloy/',
        ],
        envs=[],
        volumes=[
            {
                'host_path': f'{target_root_dir}/alloy-config',
                'container_path': '/etc/alloy',
            },
            {
                'host_path': f'{target_root_dir}/alloy-data',
                'container_path': '/var/lib/alloy/data',
            },
            {
                'host_path': '/var/run/docker.sock',
                'container_path': '/var/run/docker.sock',
            },
            {
                'host_path': '/var/log',
                'container_path': '/mnt/var/log',
                'read_only': True,
            },
        ],
        network_mode='host',
        restart='always',
        start=True,
        opts=p.ResourceOptions.merge(
            opts,
            p.ResourceOptions(depends_on=[alloy_config, alloy_data_dir_resource]),
        ),
    )

    def reload_alloy(args):
        if p.runtime.is_dry_run():
            return

        hostname = args[0]
        print(f'Reloading alloy config for {hostname}')

        req = urllib.request.Request(f'https://{hostname}/-/reload', method='POST')
        try:
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            print(f'Error reloading alloy config:\n{e.read().decode()}')
            raise

    alloy_hostname = p.Output.format('{}.{}', dns_record.name, component_config.cloudflare.zone)
    p.Output.all(alloy_hostname, alloy_config_dir_resource.id, container.id).apply(reload_alloy)
    p.export('alloy_url', alloy_hostname)
