import pydantic

import utils.model


class StrictBaseModel(pydantic.BaseModel):
    model_config = {'extra': 'forbid'}


class PulumiSecret(StrictBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class TargetConfig(StrictBaseModel):
    host: str
    user: str
    root_dir: str


class CloudflareConfig(StrictBaseModel):
    api_key: PulumiSecret | str = pydantic.Field(alias='api-key')
    email: str
    zone: str


class MinioConfig(StrictBaseModel):
    version: str


class ComponentConfig(StrictBaseModel):
    target: TargetConfig
    cloudflare: CloudflareConfig
    minio: MinioConfig


class StackConfig(StrictBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(StrictBaseModel):
    config: StackConfig
