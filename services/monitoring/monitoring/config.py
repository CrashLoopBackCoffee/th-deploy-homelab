import utils.model


class AlloyConfig(utils.model.LocalBaseModel):
    version: str
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


class TargetConfig(utils.model.LocalBaseModel):
    host: str
    user: str
    root_dir: str


class ComponentConfig(utils.model.LocalBaseModel):
    target: TargetConfig | None = None
    alloy: AlloyConfig | None = None
    cadvisor: CAdvisorConfig | None = None
    cloudflare: utils.model.CloudflareConfig | None = None
    grafana: GrafanaConfig | None = None
    mimir: MimirConfig | None = None
    speedtest_exporter: SpeedtestExporterConfig | None = None


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
