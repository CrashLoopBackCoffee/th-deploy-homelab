import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_command as command
import pulumi_kubernetes as k8s
import pulumi_onepassword as onepassword
import pulumi_proxmoxve as proxmoxve
import yaml

from kubernetes.certmanager import create_certmanager
from kubernetes.config import ComponentConfig
from kubernetes.csi_nfs import create_csi_nfs
from kubernetes.metallb import create_metallb
from kubernetes.snap import get_snap_version
from kubernetes.traefik import create_traefik
from kubernetes.util import stack_is_prod


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
            # Disk config
            'device_aliases': {
                'data': '/dev/vdb',
            },
            'disk_setup': {
                'data': {
                    'table_type': 'gpt',
                    'layout': True,
                    'overwrite': False,
                }
            },
            'fs_setup': [
                {
                    'label': 'data',
                    'filesystem': 'ext4',
                    'device': 'data',
                }
            ],
            'mounts': [
                ['LABEL=data', '/var/snap/microk8s/common/default-storage'],
            ],
            # Install packages and configure MicroK8s
            'runcmd': [
                # System update and prep
                f'hostnamectl set-hostname {hostname}',
                'apt-get update -y',
                'apt-get upgrade -y',
                f'DEBIAN_FRONTEND=noninteractive apt-get install -y {PACKAGES}',
                # MicroK8s install
                'snap install microk8s --classic',
                f'usermod -a -G microk8s {username}',
                'microk8s status --wait-ready',
                f'mkdir -p /home/{username}/.kube',
                f'chown -f -R {username}:{username} /home/{username}/.kube',
                'microk8s config > /home/ubuntu/.kube/config',
                # Start guest agent to keep Pulumi waiting until all of the above is ready
                'DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent',
                'systemctl enable qemu-guest-agent',
                'systemctl start qemu-guest-agent',
                'echo "done" /tmp/cloud-config.done',
            ],
        }
    )


def create_microk8s(
    component_config: ComponentConfig,
    cloudflare_provider: cloudflare.Provider,
    proxmox_provider: proxmoxve.Provider,
) -> None:
    proxmox_opts = p.ResourceOptions(provider=proxmox_provider)

    cloud_image = proxmoxve.download.File(
        'cloud-image',
        content_type='iso',
        datastore_id='local',
        node_name=component_config.proxmox.node_name,
        overwrite=False,
        overwrite_unmanaged=True,
        url=component_config.microk8s.cloud_image,
        opts=p.ResourceOptions.merge(proxmox_opts, p.ResourceOptions(retain_on_delete=True)),
    )

    vm_config = component_config.microk8s.master_nodes[0]
    cloud_config = proxmoxve.storage.File(
        'cloud-config',
        node_name=component_config.proxmox.node_name,
        datastore_id='local',
        content_type='snippets',
        source_raw={
            'data': _get_cloud_config(
                vm_config.name, 'ubuntu', component_config.microk8s.ssh_public_key
            ),
            'file_name': f'{vm_config.name}.yaml',
        },
        opts=p.ResourceOptions.merge(proxmox_opts, p.ResourceOptions(delete_before_replace=True)),
    )

    tags = [f'microk8s-{p.get_stack()}']
    vlan_config: proxmoxve.vm.VirtualMachineNetworkDeviceArgsDict = (
        {'vlan_id': component_config.microk8s.vlan} if component_config.microk8s.vlan else {}
    )

    p.export('microk8s-version', get_snap_version('microk8s', '1.31/stable', 'amd64'))

    gateway_address = str(vm_config.address.network.network_address + 1)
    master_vm = proxmoxve.vm.VirtualMachine(
        vm_config.name,
        name=vm_config.name,
        tags=tags,
        node_name=component_config.proxmox.node_name,
        description='MicroK8s Master',
        operating_system={
            'type': 'l26',
        },
        cpu={'cores': vm_config.cores, 'type': 'host'},
        memory={
            'floating': vm_config.memory_min,
            'dedicated': vm_config.memory_max,
        },
        cdrom={'enabled': False},
        disks=[
            # Root disk
            {
                'interface': 'virtio0',
                'size': vm_config.disks[0].size,
                'file_id': cloud_image.id,
                'iothread': True,
                'discard': 'on',
                'file_format': 'raw',
                # Hack to avoid diff in subsequent runs
                'speed': {
                    'read': 10000,
                },
            },
            # Data disks
            *[
                {
                    'interface': f'virtio{idx}',
                    'size': disk.size,
                    'iothread': True,
                    'discard': 'on',
                    'file_format': 'raw',
                    # Hack to avoid diff in subsequent runs
                    'speed': {
                        'read': 10000,
                    },
                }
                for idx, disk in enumerate(vm_config.disks[1:], start=1)
            ],
        ],
        network_devices=[{'bridge': 'vmbr0', 'model': 'virtio', **vlan_config}],
        agent={'enabled': True},
        initialization={
            'ip_configs': [
                {
                    'ipv4': {
                        'address': str(vm_config.address),
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

    # Use discovered ip address to get an implicit dependency on the VM
    connection_args = command.remote.ConnectionArgs(
        host=master_vm.ipv4_addresses[1][0],
        user='ubuntu',
    )
    kube_config_command = command.remote.Command(
        f'{vm_config.name}-kube-config',
        connection=connection_args,
        add_previous_output_in_env=False,
        create='microk8s config',
        # only log stderr and mark stdout as secret as it contains the private keys to cluster:
        logging=command.remote.Logging.STDERR,
        opts=p.ResourceOptions(additional_secret_outputs=['stdout']),
    )

    # Create kubernetes provider
    k8s_provider = k8s.Provider(
        'microk8s',
        kubeconfig=kube_config_command.stdout,
    )

    # Upgrade MicroK8s to the desired version
    command.remote.Command(
        f'{vm_config.name}-upgrade',
        connection=connection_args,
        add_previous_output_in_env=False,
        create=f'sudo snap refresh microk8s --channel {component_config.microk8s.version}',
        triggers=[get_snap_version('microk8s', component_config.microk8s.version, 'amd64')],
    )

    # Install MetalLB
    create_metallb(component_config, k8s_provider)

    # Add hostpath storage
    command.remote.Command(
        f'{vm_config.name}-storage',
        connection=connection_args,
        add_previous_output_in_env=False,
        create='microk8s enable hostpath-storage',
        delete='microk8s disable hostpath-storage',
    )

    # Install csi-driver-nfs
    create_csi_nfs(component_config, k8s_provider)

    issuer = create_certmanager(component_config, cloudflare_provider, k8s_provider)

    create_traefik(component_config, issuer, k8s_provider)

    # export to kube config with
    # p stack output --show-secrets k8s-master-0-dev-kube-config > ~/.kube/config
    p.export('kubeconfig', kube_config_command.stdout)

    onepassword.Item(
        's3-pulumi',
        title=f'Kubeconfig {p.get_stack()}',
        # Pulumi vault
        vault='mf5hvtoot2hvdylkce6hxdpqmi',
        password=kube_config_command.stdout,
    )
