import ipaddress

import utils.model


class UnifiConfig(utils.model.LocalBaseModel):
    address: ipaddress.IPv4Address
    hostname: str
    ssh_user: str
    ssh_public_key: str


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    unifi: UnifiConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
