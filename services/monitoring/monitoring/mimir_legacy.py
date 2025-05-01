"""
Deploys Grafana Mimir to the target host.
"""

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_command
import pulumi_docker as docker
import pulumi_minio as minio
import yaml

from monitoring.cloudflare import create_cloudflare_cname
from monitoring.config import ComponentConfig
from monitoring.utils import get_assets_path


def create_mimir(
    component_config: ComponentConfig,
    network: docker.Network,
    cloudflare_provider: cloudflare.Provider,
    minio_stackref: p.StackReference,
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
    create_cloudflare_cname('mimir', component_config.cloudflare.zone, cloudflare_provider)

    # Create minio provider
    minio_opts = p.ResourceOptions(
        provider=minio.Provider(
            'minio',
            minio_server=p.Output.format('{}:443', minio_stackref.get_output('minio-s3-hostname')),
            minio_user=minio_stackref.get_output('minio-user'),
            minio_password=minio_stackref.get_output('minio-password'),
            minio_ssl=True,
        )
    )

    bucket_blocks = minio.S3Bucket(
        'mimir-blocks',
        bucket='mimir-blocks',
        opts=minio_opts,
    )

    bucket_alertmanager = minio.S3Bucket(
        'mimir-alertmanager',
        bucket='mimir-alertmanager',
        opts=minio_opts,
    )

    bucket_ruler = minio.S3Bucket(
        'mimir-ruler',
        bucket='mimir-ruler',
        opts=minio_opts,
    )

    policy = {
        'Version': '2012-10-17',
        'Statement': [
            {
                'Action': ['s3:ListBucket'],
                'Effect': 'Allow',
                'Resource': [
                    bucket_blocks.arn,
                    bucket_alertmanager.arn,
                    bucket_ruler.arn,
                ],
            },
            {
                'Action': ['s3:*'],
                'Effect': 'Allow',
                'Resource': [
                    p.Output.format('{}/*', bucket_blocks.arn),
                    p.Output.format('{}/*', bucket_alertmanager.arn),
                    p.Output.format('{}/*', bucket_ruler.arn),
                ],
            },
        ],
    }
    policy = minio.IamPolicy(
        'mimir',
        policy=p.Output.json_dumps(policy),
        opts=minio_opts,
    )

    bucket_user = minio.IamUser(
        'mimir',
        opts=minio_opts,
    )

    minio.IamUserPolicyAttachment(
        'mimir',
        user_name=bucket_user.name,
        policy_name=policy.name,
        opts=minio_opts,
    )

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
            p.Output.format('AWS_ACCESS_KEY_ID={}', bucket_user.name),
            p.Output.format('AWS_SECRET_ACCESS_KEY={}', bucket_user.secret),
            p.Output.format('MINIO_HOSTNAME={}', minio_stackref.get_output('minio-s3-hostname')),
            p.Output.format('MINIO_BUCKET_ALERTMANAGER={}', bucket_alertmanager.bucket),
            p.Output.format('MINIO_BUCKET_BLOCKS={}', bucket_blocks.bucket),
            p.Output.format('MINIO_BUCKET_RULER={}', bucket_ruler.bucket),
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
