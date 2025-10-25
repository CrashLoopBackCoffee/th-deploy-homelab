import pulumi as p

from utils.k8s import get_k8s_provider

from monitoring.alloy import Alloy
from monitoring.config import ComponentConfig
from monitoring.grafana import create_grafana
from monitoring.prometheus_operator_crds import create_prometheus_operator_crds
from monitoring.speedtest import create_speedtest_exporter


def main():
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    k8s_provider = get_k8s_provider()

    assert component_config
    assert k8s_provider

    create_prometheus_operator_crds(component_config, k8s_provider)
    alloy = Alloy('default', component_config, k8s_provider)
    create_grafana(component_config, k8s_provider)
    create_speedtest_exporter(component_config, k8s_provider)

    p.export('alloy_url', alloy.url)
    p.export('alloy_lb_ip', alloy.lb_ip)
