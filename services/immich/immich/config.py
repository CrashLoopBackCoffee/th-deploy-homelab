import pydantic
import utils.model


class ImmichConfig(utils.model.LocalBaseModel):
    version: str
    library_server: str = pydantic.Field(alias='library-server')
    library_share: str = pydantic.Field(alias='library-share')
    library_mount_options: str = pydantic.Field(
        alias='library-mount-options', default='nfsvers=4.1,sec=sys'
    )


class PostgresConfig(utils.model.LocalBaseModel):
    version: str


class RedisConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    cloudflare: utils.model.CloudflareConfig
    immich: ImmichConfig
    postgres: PostgresConfig
    redis: RedisConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
