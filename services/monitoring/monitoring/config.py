import utils.model


class AlloyLegacyConfig(utils.model.LocalBaseModel):
    version: str


class AlloyConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str | None = None
    resources: utils.model.ResourcesConfig


class GrafanaCloudConfig(utils.model.LocalBaseModel):
    username: str
    token: utils.model.PulumiSecret | str


class GrafanaConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    resources: utils.model.ResourcesConfig


class MimirConfig(utils.model.LocalBaseModel):
    version: str
    resources: utils.model.ResourcesConfig


class SpeedtestExporterConfig(utils.model.LocalBaseModel):
    version: str
    resources: utils.model.ResourcesConfig


class AdGuardExporterConfig(utils.model.LocalBaseModel):
    version: str
    server: str
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef
    resources: utils.model.ResourcesConfig


class PrometheusOperatorCrdsConfig(utils.model.LocalBaseModel):
    version: str


class GoldilocksResourcesConfig(utils.model.LocalBaseModel):
    controller: utils.model.ResourcesConfig
    dashboard: utils.model.ResourcesConfig


class GoldilocksConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    resources: GoldilocksResourcesConfig


class NodeExporterConfig(utils.model.LocalBaseModel):
    version: str
    resources: utils.model.ResourcesConfig


class KubeStateMetricsConfig(utils.model.LocalBaseModel):
    version: str
    resources: utils.model.ResourcesConfig


class ComponentConfig(utils.model.LocalBaseModel):
    target: utils.model.TargetConfig
    alloy: AlloyConfig
    alloy_legacy: AlloyLegacyConfig
    cloudflare: utils.model.CloudflareConfig
    goldilocks: GoldilocksConfig
    grafana: GrafanaConfig
    grafana_cloud: GrafanaCloudConfig
    mimir: MimirConfig
    node_exporter: NodeExporterConfig
    kube_state_metrics: KubeStateMetricsConfig
    prometheus_operator_crds: PrometheusOperatorCrdsConfig
    speedtest_exporter: SpeedtestExporterConfig
    adguard_exporter: AdGuardExporterConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None = None
    config: StackConfig
