import utils.model


class CloudflareIngressConfig(utils.model.LocalBaseModel):
    service: str
    hostname: str
    set_origin_server_name: bool = False


class CloudflaredConfig(utils.model.LocalBaseModel):
    version: str
    ingress: list[CloudflareIngressConfig] = []


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    cloudflared: CloudflaredConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None
    config: StackConfig
