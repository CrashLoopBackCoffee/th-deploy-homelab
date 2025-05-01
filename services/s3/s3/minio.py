import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_command
import pulumi_docker as docker
import pulumi_minio
import pulumi_random

from s3.cloudflare import create_cloudflare_cname
from s3.config import ComponentConfig
from s3.pulumi import create_pulumi_bucket


def create_minio(
    component_config: ComponentConfig,
    network: docker.Network,
    cloudflare_provider: cloudflare.Provider,
    opts: p.ResourceOptions,
):
    """
    Deploys minio to the target host.
    """
    target_root_dir = component_config.target.root_dir
    target_host = component_config.target.host
    target_user = component_config.target.user

    # Create s3 DNS record
    create_cloudflare_cname('s3', component_config.cloudflare.zone, cloudflare_provider)
    create_cloudflare_cname('minio-console', component_config.cloudflare.zone, cloudflare_provider)

    # Create data dir
    minio_data_dir_resource = pulumi_command.remote.Command(
        'minio-data-dir',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/minio-data',
    )

    image = docker.RemoteImage(
        'minio',
        name=f'quay.io/minio/minio:{component_config.minio.version}',
        keep_locally=True,
        opts=opts,
    )

    # Create random password
    minio_password = pulumi_random.RandomPassword(
        'minio-password',
        length=16,
        special=True,
        opts=opts,
    )

    docker.Container(
        'minio',
        name='minio',
        image=image.image_id,
        command=['server', '/data', '--console-address', ':9001'],
        envs=[
            'MINIO_ROOT_USER=admin',
            p.Output.format('MINIO_ROOT_PASSWORD={}', minio_password.result),
        ],
        networks_advanced=[
            {'name': network.name, 'aliases': ['minio']},
        ],
        ports=[
            {'internal': 9000, 'external': 9000},
            {'internal': 9001, 'external': 9001},
        ],
        volumes=[
            {
                'host_path': f'{target_root_dir}/minio-data',
                'container_path': '/data',
            },
        ],
        restart='always',
        start=True,
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[minio_data_dir_resource])),
    )

    minio_provider = pulumi_minio.Provider(
        'minio',
        minio_server=f's3.{component_config.cloudflare.zone}:443',
        minio_user='admin',
        minio_password=minio_password.result,
        minio_ssl=True,
    )

    create_pulumi_bucket(minio_provider)

    p.export('minio-s3', f'https://s3.{component_config.cloudflare.zone}')
    p.export('minio-s3-hostname', f's3.{component_config.cloudflare.zone}')
    p.export('minio-console', f'https://minio-console.{component_config.cloudflare.zone}')
    p.export('minio-user', 'admin')
    p.export('minio-password', minio_password.result)
