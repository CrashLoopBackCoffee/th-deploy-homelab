import pathlib

import deploy_base.model
import pydantic

REPO_PREFIX = 'deploy-'


def get_pulumi_project():
    repo_dir = pathlib.Path().resolve()

    while not repo_dir.name.startswith(REPO_PREFIX):
        if not repo_dir.parents:
            raise ValueError('Could not find repo root')

        repo_dir = repo_dir.parent
    return repo_dir.name[len(REPO_PREFIX) :]


class PulumiSecret(deploy_base.model.LocalBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class EntraIdConfig(deploy_base.model.LocalBaseModel):
    tenant_id: str = 'ac1df362-04cf-4e6e-839b-031c16ada473'
    client_id: str
    client_secret: str | PulumiSecret


class GoogleConfig(deploy_base.model.LocalBaseModel):
    client_id: str
    client_secret: str | PulumiSecret


class RedisConfig(deploy_base.model.LocalBaseModel):
    version: str


class TikaConfig(deploy_base.model.LocalBaseModel):
    version: str


class GotenbergConfig(deploy_base.model.LocalBaseModel):
    version: str


class PostgresConfig(deploy_base.model.LocalBaseModel):
    version: str


class MailConfig(deploy_base.model.LocalBaseModel):
    client_id: str
    client_secret: str | PulumiSecret


class PaperlessConfig(deploy_base.model.LocalBaseModel):
    version: str

    consume_server: str = pydantic.Field(alias='consume-server')
    consume_share: str = pydantic.Field(alias='consume-share')
    consume_mount_options: str = pydantic.Field(
        alias='consume-mount-options', default='nfsvers=4.1,sec=sys'
    )


class ComponentConfig(deploy_base.model.LocalBaseModel):
    kubeconfig: deploy_base.model.OnePasswordRef
    cloudflare: deploy_base.model.CloudflareConfig
    paperless: PaperlessConfig
    redis: RedisConfig
    entraid: EntraIdConfig
    google: GoogleConfig
    mail: MailConfig
    postgres: PostgresConfig
    tika: TikaConfig
    gotenberg: GotenbergConfig


class StackConfig(deploy_base.model.LocalBaseModel):
    model_config = {'alias_generator': lambda field_name: f'{get_pulumi_project()}:{field_name}'}
    config: ComponentConfig


class PulumiConfigRoot(deploy_base.model.LocalBaseModel):
    config: StackConfig
