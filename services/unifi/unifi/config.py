import ipaddress

import pydantic

import utils.model

REPO_PREFIX = 'deploy-'


class PulumiSecret(utils.model.LocalBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class ProxmoxConfig(utils.model.LocalBaseModel):
    api_token: utils.model.OnePasswordRef
    api_endpoint: str
    node_name: str
    insecure: bool = False


class UnifiConfig(utils.model.LocalBaseModel):
    version: str
    cloud_image: str = pydantic.Field(
        default='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
    )
    address: ipaddress.IPv4Interface
    vlan: int | None = None
    hostname: str
    ssh_public_key: str
    cores: int = 2
    memory_min: int = 1024
    memory_max: int = 2048
    disk_size: int = 20


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    proxmox: ProxmoxConfig
    unifi: UnifiConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
