import pydantic

import utils.model


class EntraIdConfig(utils.model.LocalBaseModel):
    tenant_id: str = 'ac1df362-04cf-4e6e-839b-031c16ada473'
    client_id: str
    client_secret: str | utils.model.PulumiSecret


class GoogleConfig(utils.model.LocalBaseModel):
    client_id: str
    client_secret: str | utils.model.PulumiSecret


class RedisConfig(utils.model.LocalBaseModel):
    version: str


class TikaConfig(utils.model.LocalBaseModel):
    version: str


class GotenbergConfig(utils.model.LocalBaseModel):
    version: str


class PostgresConfig(utils.model.LocalBaseModel):
    version: str


class MailConfig(utils.model.LocalBaseModel):
    client_id: str
    client_secret: str | utils.model.PulumiSecret


class PaperlessConfig(utils.model.LocalBaseModel):
    version: str

    consume_server: str = pydantic.Field(alias='consume-server')
    consume_share: str = pydantic.Field(alias='consume-share')
    consume_mount_options: str = pydantic.Field(
        alias='consume-mount-options', default='nfsvers=4.1,sec=sys'
    )


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    cloudflare: utils.model.CloudflareConfig
    paperless: PaperlessConfig
    redis: RedisConfig
    entraid: EntraIdConfig
    google: GoogleConfig
    mail: MailConfig
    postgres: PostgresConfig
    tika: TikaConfig
    gotenberg: GotenbergConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
