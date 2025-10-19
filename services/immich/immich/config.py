import pydantic
import utils.model


class ImmichConfig(utils.model.LocalBaseModel):
    version: str
    chart_version: str
    library_server: str
    library_share: str
    library_mount_options: str = pydantic.Field(
        alias='library-mount-options', default='nfsvers=4.1,sec=sys'
    )
    library_pvc_name: str = pydantic.Field(default='immich-library')


class PostgresConfig(utils.model.LocalBaseModel):
    vectorchord_version: str


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    cloudflare: utils.model.CloudflareConfig
    immich: ImmichConfig
    postgres: PostgresConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
