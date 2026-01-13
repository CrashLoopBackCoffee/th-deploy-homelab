import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_command
import pulumi_docker as docker
import utils.cloudflare

from netboot.config import ComponentConfig


def create_netboot(
    component_config: ComponentConfig,
    network: docker.Network,
    cloudflare_provider: cloudflare.Provider,
    opts: p.ResourceOptions,
):
    """
    Deploys netboot.xyz to the target host.
    """
    target_root_dir = component_config.target.root_dir
    target_host = component_config.target.host
    target_user = component_config.target.user

    # Create s3 DNS record
    utils.cloudflare.create_cloudflare_cname(
        'netboot', component_config.cloudflare.zone, cloudflare_provider
    )

    # Create config and assets directories
    netboot_config_dir_resource = pulumi_command.remote.Command(
        'netboot-config-dir',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/netboot-config',
    )

    netboot_assets_dir_resource = pulumi_command.remote.Command(
        'netboot-assets-dir',
        connection=pulumi_command.remote.ConnectionArgs(host=target_host, user=target_user),
        create=f'mkdir -p {target_root_dir}/netboot-assets',
    )

    image = docker.RemoteImage(
        'netboot',
        name=f'ghcr.io/netbootxyz/netbootxyz:{component_config.netboot.version}',
        keep_locally=True,
        opts=opts,
    )

    docker.Container(
        'netboot',
        name='netboot',
        image=image.image_id,
        envs=[
            f'NGINX_PORT={component_config.netboot.nginx_port}',
            f'WEB_APP_PORT={component_config.netboot.web_port}',
        ],
        network_mode='host',
        volumes=[
            {
                'host_path': f'{target_root_dir}/netboot-config',
                'container_path': '/config',
            },
            {
                'host_path': f'{target_root_dir}/netboot-assets',
                'container_path': '/assets',
            },
        ],
        restart='always',
        start=True,
        opts=p.ResourceOptions.merge(
            opts,
            p.ResourceOptions(
                depends_on=[netboot_config_dir_resource, netboot_assets_dir_resource]
            ),
        ),
    )

    p.export(
        'netboot-url',
        p.Output.format('https://netboot.{}', component_config.cloudflare.zone),
    )
    p.export('netboot-web-port', component_config.netboot.web_port)
    p.export('netboot-tftp-port', component_config.netboot.tftp_port)
    p.export('netboot-nginx-port', component_config.netboot.nginx_port)
