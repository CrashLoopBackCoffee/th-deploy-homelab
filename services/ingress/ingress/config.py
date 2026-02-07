import utils.model


class SynologyCertConfig(utils.model.LocalBaseModel):
    hostname: str


class SynologyConfig(utils.model.LocalBaseModel):
    host: str
    port: int = 5000
    scheme: str = 'http'
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef
    certs: list[SynologyCertConfig] = []


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
    local_cloudflared: list[CloudflareIngressConfig] = []
    synology: SynologyConfig | None = None


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None
    config: StackConfig
