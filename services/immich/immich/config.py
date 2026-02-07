import pydantic
import utils.model


class PersistenceShareConfig(utils.model.LocalBaseModel):
    nfs_server: str = pydantic.Field(alias='nfs-server')
    nfs_path: str = pydantic.Field(alias='nfs-path')
    nfs_mount_options: str = pydantic.Field(
        alias='nfs-mount-options', default='nfsvers=4.1,sec=sys'
    )
    size: str = '100Gi'


class ImmichConfig(utils.model.LocalBaseModel):
    version: str
    chart_version: str
    persistence: dict[str, PersistenceShareConfig]
    preload_model: str = ''


class PostgresConfig(utils.model.LocalBaseModel):
    version: str
    vectorchord_version: str
    backup: utils.model.PostgresBackupConfig | None = None


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    immich: ImmichConfig
    postgres: PostgresConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None
    config: StackConfig
