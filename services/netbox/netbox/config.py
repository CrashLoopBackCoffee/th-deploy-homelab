import utils.model


class NetboxSuperuserConfig(utils.model.LocalBaseModel):
    name: str = 'admin'
    email: str = 'admin@example.com'


class NetboxStorageConfig(utils.model.LocalBaseModel):
    valkey_size: str = '8Gi'


class NetboxResourcesConfig(utils.model.LocalBaseModel):
    netbox: utils.model.ResourcesConfig
    worker: utils.model.ResourcesConfig
    housekeeping: utils.model.ResourcesConfig
    valkey: utils.model.ResourcesConfig


class PostgresConfig(utils.model.LocalBaseModel):
    version: int


class NetboxConfig(utils.model.LocalBaseModel):
    chart_version: str
    superuser: NetboxSuperuserConfig = NetboxSuperuserConfig()
    storage: NetboxStorageConfig = NetboxStorageConfig()
    resources: NetboxResourcesConfig


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    netbox: NetboxConfig
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
