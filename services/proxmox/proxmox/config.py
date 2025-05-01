import pydantic

import utils.model


class PulumiSecret(utils.model.LocalBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class CloudflareConfig(utils.model.LocalBaseModel):
    api_key: PulumiSecret | str
    email: str
    zone: str


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: CloudflareConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
