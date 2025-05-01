import pydantic

import utils.model


class PulumiSecret(utils.model.LocalBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class AlloyConfig(utils.model.LocalBaseModel):
    version: str
    username: str
    token: PulumiSecret | str


class GrafanaConfig(utils.model.LocalBaseModel):
    version: str

    hostname: str | None = None


class CloudflareConfig(utils.model.LocalBaseModel):
    api_key: PulumiSecret | str = pydantic.Field(alias='api-key')
    email: str
    zone: str


class MimirConfig(utils.model.LocalBaseModel):
    version: str


class PrometheusConfig(utils.model.LocalBaseModel):
    version: str


class SpeedtestExporterConfig(utils.model.LocalBaseModel):
    version: str


class TargetConfig(utils.model.LocalBaseModel):
    host: str
    user: str
    root_dir: str


class ComponentConfig(utils.model.LocalBaseModel):
    target: TargetConfig | None = None
    alloy: AlloyConfig | None = None
    cloudflare: CloudflareConfig | None = None
    grafana: GrafanaConfig | None = None
    mimir: MimirConfig | None = None
    prometheus: PrometheusConfig | None = None
    speedtest_exporter: SpeedtestExporterConfig | None = None


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
