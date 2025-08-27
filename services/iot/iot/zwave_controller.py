import pulumi as p
import pulumi_docker as docker
import pulumi_proxmoxve as proxmoxve
import pulumi_random
import yaml

import utils.opnsense.unbound.host_override
import utils.utils

from iot.config import ComponentConfig


def _get_cloud_config(hostname: str, username: str, ssh_public_key: str) -> str:
    PACKAGES = ' '.join(
        [
            'apt-transport-https',
            'ca-certificates',
            'curl',
            'gpg',
            'linux-generic',
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
                'apt-get install -y docker.io docker-compose',
                f'usermod -a -G docker {username}',
                # Start guest agent to keep Pulumi waiting until all of the above is ready
                'DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent',
                'systemctl enable qemu-guest-agent',
                'systemctl start qemu-guest-agent',
                'echo "done" /tmp/cloud-config.done',
            ],
        }
    )


class ZwaveeController(p.ComponentResource):
    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        proxmox_provider: proxmoxve.Provider,
    ):
        super().__init__(f'lab:zwave-controller:{name}', name)

        proxmox_opts = p.ResourceOptions(provider=proxmox_provider, parent=self)

        # Create local DNS record
        utils.opnsense.unbound.host_override.HostOverride(
            'zwave-controller',
            host=component_config.zwave_controller.hostname.split('.', 1)[0],
            domain=component_config.zwave_controller.hostname.split('.', 1)[1],
            record_type='A',
            ipaddress=str(component_config.zwave_controller.address.ip),
        )

        cloud_image = proxmoxve.download.File(
            'cloud-image',
            content_type='iso',
            datastore_id='local',
            node_name=component_config.proxmox.node_name,
            overwrite=False,
            overwrite_unmanaged=True,
            url=component_config.zwave_controller.cloud_image,
            opts=p.ResourceOptions.merge(proxmox_opts, p.ResourceOptions(retain_on_delete=True)),
        )

        cloud_config = proxmoxve.storage.File(
            'cloud-config',
            node_name=component_config.proxmox.node_name,
            datastore_id='local',
            content_type='snippets',
            source_raw={
                'data': _get_cloud_config(
                    f'unifi-{p.get_stack()}',
                    'ubuntu',
                    component_config.zwave_controller.ssh_public_key,
                ),
                'file_name': f'unifi-{p.get_stack()}.yaml',
            },
            opts=p.ResourceOptions.merge(
                proxmox_opts,
                p.ResourceOptions(
                    delete_before_replace=True,
                    # Hack since this is not really our file but updating it forces recreation of the VM
                    retain_on_delete=True,
                ),
            ),
        )

        tags = [f'zwave-controller-{p.get_stack()}']
        vlan_config: proxmoxve.vm.VirtualMachineNetworkDeviceArgsDict = (
            {'vlan_id': component_config.zwave_controller.vlan}
            if component_config.zwave_controller.vlan
            else {}
        )
        gateway_address = str(component_config.zwave_controller.address.network.network_address + 1)

        vm = proxmoxve.vm.VirtualMachine(
            f'zwave-controller-{p.get_stack()}',
            name=f'zwave-controller-{p.get_stack()}',
            tags=tags,
            node_name=component_config.proxmox.node_name,
            description='Zwave Controller',
            operating_system={
                'type': 'l26',
            },
            cpu={'cores': component_config.zwave_controller.cores, 'type': 'host'},
            memory={
                'floating': component_config.zwave_controller.memory_min,
                'dedicated': component_config.zwave_controller.memory_max,
            },
            cdrom={'enabled': False},
            disks=[
                # Root disk
                {
                    'interface': 'virtio0',
                    'size': component_config.zwave_controller.disk_size,
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
            usbs=[
                proxmoxve.vm.VirtualMachineUsbArgs(
                    host=component_config.zwave_controller.zwave_adapter.usb_id,
                ),
            ],
            agent={'enabled': True},
            initialization={
                'ip_configs': [
                    {
                        'ipv4': {
                            'address': str(component_config.zwave_controller.address),
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
            on_boot=utils.utils.stack_is_prod(),
            protection=utils.utils.stack_is_prod(),
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
        docker_opts = p.ResourceOptions(provider=docker_provider, parent=self)

        # Create zwave-js-ui container
        image = docker.RemoteImage(
            'zwave-js-ui',
            name=f'zwavejs/zwave-js-ui:{component_config.zwave_controller.version}',
            keep_locally=True,
            opts=docker_opts,
        )
        session_secret = pulumi_random.RandomPassword(
            'session-secret',
            length=32,
        )

        volume = docker.Volume(
            'zwave-config',
            name='zwave-config',
            opts=docker_opts,
        )

        docker.Container(
            'zwave-js-ui',
            image=image.image_id,
            name='zwave-js-ui',
            restart='unless-stopped',
            network_mode='host',
            tty=True,
            envs=[p.Output.format('SESSION_SECRET={}', session_secret.result)],
            devices=[
                {
                    'host_path': f'/dev/serial/by-id/{component_config.zwave_controller.zwave_adapter.serial_id}',
                    'container_path': '/dev/zwave',
                }
            ],
            volumes=[
                {
                    'volume_name': volume.name,
                    'container_path': '/usr/src/app/store',
                }
            ],
            opts=docker_opts,
        )
