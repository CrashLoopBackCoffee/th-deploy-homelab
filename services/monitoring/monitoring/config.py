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


class AlloyConfig(deploy_base.model.LocalBaseModel):
    version: str
    username: str
    token: PulumiSecret | str


class GrafanaConfig(deploy_base.model.LocalBaseModel):
    version: str

    hostname: str | None = None


class CloudflareConfig(deploy_base.model.LocalBaseModel):
    api_key: PulumiSecret | str = pydantic.Field(alias='api-key')
    email: str
    zone: str


class MimirConfig(deploy_base.model.LocalBaseModel):
    version: str


class PrometheusConfig(deploy_base.model.LocalBaseModel):
    version: str


class SpeedtestExporterConfig(deploy_base.model.LocalBaseModel):
    version: str


class TargetConfig(deploy_base.model.LocalBaseModel):
    host: str
    user: str
    root_dir: str


class ComponentConfig(deploy_base.model.LocalBaseModel):
    target: TargetConfig | None = None
    alloy: AlloyConfig | None = None
    cloudflare: CloudflareConfig | None = None
    grafana: GrafanaConfig | None = None
    mimir: MimirConfig | None = None
    prometheus: PrometheusConfig | None = None
    speedtest_exporter: SpeedtestExporterConfig | None = None


class StackConfig(deploy_base.model.LocalBaseModel):
    model_config = {'alias_generator': lambda field_name: f'{get_pulumi_project()}:{field_name}'}
    config: ComponentConfig


class PulumiConfigRoot(deploy_base.model.LocalBaseModel):
    config: StackConfig
