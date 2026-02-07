import utils.model


class TandoorConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str


class PostgresConfig(utils.model.LocalBaseModel):
    version: int
    backup: utils.model.PostgresBackupConfig | None = None


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    tandoor: TandoorConfig
    postgres: PostgresConfig


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
