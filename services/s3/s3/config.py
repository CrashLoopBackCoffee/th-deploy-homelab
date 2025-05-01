import utils.model


class TargetConfig(utils.model.LocalBaseModel):
    host: str
    user: str
    root_dir: str


class MinioConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    target: TargetConfig
    cloudflare: utils.model.CloudflareConfig
    minio: MinioConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
