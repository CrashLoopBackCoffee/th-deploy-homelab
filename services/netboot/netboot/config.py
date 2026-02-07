import utils.model


class NetbootConfig(utils.model.LocalBaseModel):
    version: str
    menu_version: str = '2.0.84'
    web_port: int = 3000
    tftp_port: int = 69
    nginx_port: int = 8080


class ComponentConfig(utils.model.LocalBaseModel):
    target: utils.model.TargetConfig
    cloudflare: utils.model.CloudflareConfig
    netboot: NetbootConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
