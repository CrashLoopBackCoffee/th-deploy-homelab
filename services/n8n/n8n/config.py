import utils.model


class N8nConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    webhook_url: str = ''
    resources: utils.model.ResourcesConfig


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    n8n: N8nConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None = None
    config: StackConfig
