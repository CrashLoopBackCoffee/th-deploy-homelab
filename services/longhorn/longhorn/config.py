import utils.model


class LonghornConfig(utils.model.LocalBaseModel):
    chart_version: str
    hostname: str | None = None


class S3Config(utils.model.LocalBaseModel):
    endpoint: utils.model.OnePasswordRef
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    longhorn: LonghornConfig
    s3: S3Config


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
