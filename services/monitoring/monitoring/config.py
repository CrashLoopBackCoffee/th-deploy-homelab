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

    hostname: str


class MimirConfig(utils.model.LocalBaseModel):
    version: str


class SpeedtestExporterConfig(utils.model.LocalBaseModel):
    version: str


class PrometheusOperatorCrdsConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    target: utils.model.TargetConfig
    alloy: AlloyConfig
    alloy_legacy: AlloyLegacyConfig
    cadvisor_legacy: CAdvisorConfig
    cloudflare: utils.model.CloudflareConfig
    grafana: GrafanaConfig
    grafana_cloud: GrafanaCloudConfig
    mimir: MimirConfig
    prometheus_operator_crds: PrometheusOperatorCrdsConfig
    speedtest_exporter: SpeedtestExporterConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None = None
    config: StackConfig
