import pulumi as p
import pulumi_proxmoxve as proxmoxve


def get_proxmox_provider():
    proxmox_config = p.Config().require_object('proxmox')

    return proxmoxve.Provider(
        'proxmox',
        endpoint=proxmox_config['api-endpoint'],
        api_token=proxmox_config['api-token'],
        insecure=proxmox_config.get('insecure', False),
        ssh={
            'username': 'root',
            'agent': True,
        },
    )
