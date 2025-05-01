import ipaddress

import pydantic

import utils.model

REPO_PREFIX = 'deploy-'


class StrictBaseModel(pydantic.BaseModel):
    model_config = {'extra': 'forbid'}


class PulumiSecret(StrictBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class ProxmoxConfig(StrictBaseModel):
    api_token: utils.model.OnePasswordRef = pydantic.Field(alias='api-token')
    api_endpoint: str = pydantic.Field(alias='api-endpoint')
    node_name: str = pydantic.Field(alias='node-name')
    insecure: bool = False


class UnifiConfig(StrictBaseModel):
    version: str
    cloud_image: str = pydantic.Field(
        alias='cloud-image',
        default='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
    )
    address: ipaddress.IPv4Interface
    vlan: int | None = None
    hostname: str
    ssh_public_key: str = pydantic.Field(alias='ssh-public-key')
    cores: int = 2
    memory_min: int = 1024
    memory_max: int = 2048
    disk_size: int = 20


class ComponentConfig(StrictBaseModel):
    cloudflare: utils.model.CloudflareConfig
    proxmox: ProxmoxConfig
    unifi: UnifiConfig


class StackConfig(StrictBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(StrictBaseModel):
    config: StackConfig
