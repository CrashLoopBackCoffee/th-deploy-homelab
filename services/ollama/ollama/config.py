import utils.model


class OllamaResourcesConfig(utils.model.LocalBaseModel):
    memory: str = '8Gi'
    cpu: str = '4'


class OllamaConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    resources: OllamaResourcesConfig = OllamaResourcesConfig()


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    ollama: OllamaConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
