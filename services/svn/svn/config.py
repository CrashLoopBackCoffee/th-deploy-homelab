import utils.model


class SvnConfig(utils.model.LocalBaseModel):
    # Full image tag including variant (e.g. "httpd-1.14.2")
    version: str
    resources: utils.model.ResourcesConfig


class ComponentConfig(utils.model.LocalBaseModel):
    svn: SvnConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str]
    config: StackConfig
