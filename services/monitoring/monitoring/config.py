import utils.model


class AlloyLegacyConfig(utils.model.LocalBaseModel):
    version: str


class AlloyConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str | None = None


class GrafanaCloudConfig(utils.model.LocalBaseModel):
    username: str
    token: utils.model.PulumiSecret | str


class CAdvisorConfig(utils.model.LocalBaseModel):
    version: str


class GrafanaConfig(utils.model.LocalBaseModel):
    version: str

    hostname: str | None = None


class MimirConfig(utils.model.LocalBaseModel):
    version: str


class SpeedtestExporterConfig(utils.model.LocalBaseModel):
    version: str


class PrometheusOperatorCrdsConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    target: utils.model.TargetConfig | None = None
    alloy: AlloyConfig | None = None
    alloy_legacy: AlloyLegacyConfig | None = None
    cadvisor: CAdvisorConfig | None = None
    cloudflare: utils.model.CloudflareConfig | None = None
    grafana: GrafanaConfig | None = None
    grafana_cloud: GrafanaCloudConfig | None = None
    mimir: MimirConfig | None = None
    prometheus_operator_crds: PrometheusOperatorCrdsConfig
    speedtest_exporter: SpeedtestExporterConfig | None = None


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None = None
    config: StackConfig
