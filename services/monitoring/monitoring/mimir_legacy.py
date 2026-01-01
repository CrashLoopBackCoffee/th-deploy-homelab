"""
Deploys Grafana Mimir to the target host.
"""

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_command
import pulumi_docker as docker
import utils.cloudflare
import yaml

from monitoring.config import ComponentConfig
from monitoring.mimir_buckets import MimirBuckets
from monitoring.utils import get_assets_path


def create_mimir_legacy(
    component_config: ComponentConfig,
    network: docker.Network,
    cloudflare_provider: cloudflare.Provider,
    mimir_buckets: MimirBuckets,
    opts: p.ResourceOptions,
):
    """
    Deploys Grafana Mimir to the target host.
    """
    assert component_config.target
    assert component_config.cloudflare
    assert component_config.mimir
    target_root_dir = component_config.target.root_dir
    target_host = component_config.target.host
    target_user = component_config.target.user

    # Create mimir DNS record
    utils.cloudflare.create_cloudflare_cname(
        'mimir', component_config.cloudflare.zone, cloudflare_provider
    )

    s3_config = p.Config().require_object('s3')

    # Create mimir-config folder
    mimir_path = get_assets_path() / 'mimir'
    mimir_config_dir_resource = pulumi_command.remote.Command(
        'create-mimir-config',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/mimir-config',
    )
    mimir_data_dir_resource = pulumi_command.remote.Command(
        'create-mimir-data',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/mimir-data',
    )

    sync_command = (
        f'rsync --rsync-path /bin/rsync -av --delete '
        f'{mimir_path}/ '
        f'{target_user}@{target_host}:{target_root_dir}/mimir-config/'
    )
    with open(mimir_path / 'config.yaml', 'r', encoding='UTF-8') as f:
        mimir_config = yaml.safe_load(f.read())
    pulumi_command.local.Command(
        'mimir-config',
        create=sync_command,
        triggers=[mimir_config, mimir_config_dir_resource.id],
    )

    image = docker.RemoteImage(
        'mimir',
        name=f'grafana/mimir:{component_config.mimir.version}',
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        'mimir',
        image=image.image_id,
        name='mimir',
        command=[
            '--config.file=/etc/mimir/config.yaml',
            '--config.expand-env=true',
        ],
        envs=[
            p.Output.format('AWS_ACCESS_KEY_ID={}', mimir_buckets.bucket_user.name),
            p.Output.format('AWS_SECRET_ACCESS_KEY={}', mimir_buckets.bucket_user.secret),
            p.Output.format('MINIO_HOSTNAME={}', s3_config['endpoint']),
            p.Output.format(
                'MINIO_BUCKET_ALERTMANAGER={}', mimir_buckets.bucket_alertmanager.bucket
            ),
            p.Output.format('MINIO_BUCKET_BLOCKS={}', mimir_buckets.bucket_blocks.bucket),
            p.Output.format('MINIO_BUCKET_RULER={}', mimir_buckets.bucket_ruler.bucket),
        ],
        ports=[
            {'internal': 9009, 'external': 9009},
            {'internal': 9095, 'external': 9095},
        ],
        volumes=[
            {
                'host_path': f'{target_root_dir}/mimir-config/config.yaml',
                'container_path': '/etc/mimir/config.yaml',
                'read_only': True,
            },
            {
                'host_path': f'{target_root_dir}/mimir-data',
                'container_path': '/data',
            },
        ],
        networks_advanced=[
            {'name': network.name, 'aliases': ['mimir']},
        ],
        restart='always',
        start=True,
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[mimir_data_dir_resource])),
    )
