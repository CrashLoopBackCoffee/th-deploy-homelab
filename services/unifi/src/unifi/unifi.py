import deploy_base.opnsense.unbound.host_override
import pulumi as p
import pulumi_command
import pulumi_docker as docker
import pulumi_proxmoxve as proxmoxve
import pulumiverse_acme as acme
import yaml

from unifi.config import ComponentConfig
from unifi.utils import stack_is_prod


def _get_cloud_config(hostname: str, username: str, ssh_public_key: str) -> str:
    PACKAGES = ' '.join(
        [
            'apt-transport-https',
            'ca-certificates',
            'curl',
            'gpg',
            'net-tools',
            'vim',
        ]
    )
    return '#cloud-config\n' + yaml.safe_dump(
        {
            # User config
            'users': [
                'default',
                {
                    'name': username,
                    'groups': ['sudo'],
                    'shell': '/bin/bash',
                    'ssh_authorized_keys': [ssh_public_key],
                    'lock_passwd': True,
                    'sudo': ['ALL=(ALL) NOPASSWD:ALL'],
                },
            ],
            # Install packages and configure MicroK8s
            'runcmd': [
                # System update and prep
                f'hostnamectl set-hostname {hostname}',
                'apt-get update -y',
                'apt-get upgrade -y',
                f'DEBIAN_FRONTEND=noninteractive apt-get install -y {PACKAGES}',
                # Install docker
                'apt-get install -y docker.io',
                f'usermod -a -G docker {username}',
                # Start guest agent to keep Pulumi waiting until all of the above is ready
                'DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent',
                'systemctl enable qemu-guest-agent',
                'systemctl start qemu-guest-agent',
                'echo "done" /tmp/cloud-config.done',
            ],
        }
    )


def create_unifi(
    component_config: ComponentConfig,
    certificate: acme.Certificate,
    proxmox_provider: proxmoxve.Provider,
):
    proxmox_opts = p.ResourceOptions(provider=proxmox_provider)

    # Create local DNS record
    deploy_base.opnsense.unbound.host_override.HostOverride(
        'unifi',
        host=component_config.unifi.hostname.split('.', 1)[0],
        domain=component_config.unifi.hostname.split('.', 1)[1],
        record_type='A',
        ipaddress=str(component_config.unifi.address.ip),
    )

    cloud_image = proxmoxve.download.File(
        'cloud-image',
        content_type='iso',
        datastore_id='local',
        node_name=component_config.proxmox.node_name,
        overwrite=False,
        overwrite_unmanaged=True,
        url=component_config.unifi.cloud_image,
        opts=p.ResourceOptions.merge(proxmox_opts, p.ResourceOptions(retain_on_delete=True)),
    )

    cloud_config = proxmoxve.storage.File(
        'cloud-config',
        node_name=component_config.proxmox.node_name,
        datastore_id='local',
        content_type='snippets',
        source_raw={
            'data': _get_cloud_config(
                f'unifi-{p.get_stack()}', 'ubuntu', component_config.unifi.ssh_public_key
            ),
            'file_name': f'unifi-{p.get_stack()}.yaml',
        },
        opts=p.ResourceOptions.merge(proxmox_opts, p.ResourceOptions(delete_before_replace=True)),
    )

    tags = [f'unifi-{p.get_stack()}']
    vlan_config: proxmoxve.vm.VirtualMachineNetworkDeviceArgsDict = (
        {'vlan_id': component_config.unifi.vlan} if component_config.unifi.vlan else {}
    )
    gateway_address = str(component_config.unifi.address.network.network_address + 1)

    vm = proxmoxve.vm.VirtualMachine(
        f'unifi-{p.get_stack()}',
        name=f'unifi-{p.get_stack()}',
        tags=tags,
        node_name=component_config.proxmox.node_name,
        description='Unifi Controller',
        operating_system={
            'type': 'l26',
        },
        cpu={'cores': component_config.unifi.cores, 'type': 'host'},
        memory={
            'floating': component_config.unifi.memory_min,
            'dedicated': component_config.unifi.memory_max,
        },
        cdrom={'enabled': False},
        disks=[
            # Root disk
            {
                'interface': 'virtio0',
                'size': component_config.unifi.disk_size,
                'file_id': cloud_image.id,
                'iothread': True,
                'discard': 'on',
                'file_format': 'raw',
                # Hack to avoid diff in subsequent runs
                'speed': {
                    'read': 10000,
                },
            },
        ],
        network_devices=[{'bridge': 'vmbr0', 'model': 'virtio', **vlan_config}],
        agent={'enabled': True},
        initialization={
            'ip_configs': [
                {
                    'ipv4': {
                        'address': str(component_config.unifi.address),
                        'gateway': gateway_address,
                    },
                },
            ],
            'dns': {
                'domain': 'local',
                'servers': [gateway_address],
            },
            'user_data_file_id': cloud_config.id,
        },
        stop_on_destroy=True,
        on_boot=stack_is_prod(),
        protection=stack_is_prod(),
        machine='q35',
        opts=p.ResourceOptions.merge(proxmox_opts, p.ResourceOptions(ignore_changes=['cdrom'])),
    )

    unifi_host = vm.ipv4_addresses[1][0]
    docker_provider = docker.Provider(
        'docker',
        host=p.Output.format(
            'ssh://ubuntu@{}',
            unifi_host,
        ),
        ssh_opts=[
            '-o StrictHostKeyChecking=no',
            '-o UserKnownHostsFile=/dev/null',
        ],
    )

    # Create unifi folders
    connection = pulumi_command.remote.ConnectionArgs(host=unifi_host, user='ubuntu')
    unifi_cert_path = '/unifi/cert'
    unifi_cert_dir_resource = pulumi_command.remote.Command(
        'create-unifi-cert',
        connection=connection,
        create=f'sudo mkdir -p {unifi_cert_path}',
    )
    unifi_data_path = '/unifi/data'
    unifi_data_dir_resource = pulumi_command.remote.Command(
        'create-unifi-data',
        connection=connection,
        create=f'sudo mkdir -p {unifi_data_path}',
    )
    unifi_log_path = '/unifi/log'
    unifi_log_dir_resource = pulumi_command.remote.Command(
        'create-unifi-log',
        connection=connection,
        create=f'sudo mkdir -p {unifi_log_path}',
    )

    # Create unifi cert
    private_key_resource = pulumi_command.remote.Command(
        'create-unifi-tls-key',
        connection=connection,
        stdin=certificate.private_key_pem,
        create=f'sudo sed -n "w {unifi_cert_path}/privkey.pem"',
        triggers=[certificate],
        opts=p.ResourceOptions(depends_on=[unifi_cert_dir_resource]),
    )
    certificate_resource = pulumi_command.remote.Command(
        'create-unifi-tls-cert',
        connection=connection,
        stdin=certificate.certificate_pem,
        create=f'sudo sed -n "w {unifi_cert_path}/cert.pem"',
        triggers=[certificate],
        opts=p.ResourceOptions(depends_on=[unifi_cert_dir_resource]),
    )
    chain_resource = pulumi_command.remote.Command(
        'create-unifi-tls-chain',
        connection=connection,
        stdin=certificate.issuer_pem,
        create=f'sudo sed -n "w {unifi_cert_path}/chain.pem"',
        triggers=[certificate],
        opts=p.ResourceOptions(depends_on=[unifi_cert_dir_resource]),
    )

    # Create unifi container
    docker_opts = p.ResourceOptions(provider=docker_provider, deleted_with=vm)
    image = docker.RemoteImage(
        'cadvisor',
        name=f'jacobalberty/unifi:v{component_config.unifi.version}',
        keep_locally=True,
        opts=docker_opts,
    )

    docker.Container(
        'unifi',
        image=image.image_id,
        name='unifi',
        envs=[
            'UNIFI_STDOUT=true',
            'TZ=Europe/Berlin',
            'UNIFI_HTTPS_PORT=8443',
        ],
        init=True,
        volumes=[
            {
                'host_path': '/unifi',
                'container_path': '/unifi',
            },
        ],
        network_mode='host',
        user='unifi',
        restart='always',
        start=True,
        opts=p.ResourceOptions.merge(
            docker_opts,
            p.ResourceOptions(
                depends_on=[
                    unifi_cert_dir_resource,
                    unifi_data_dir_resource,
                    unifi_log_dir_resource,
                    private_key_resource,
                    certificate_resource,
                    chain_resource,
                ]
            ),
        ),
    )
