import pulumi as p
import pulumi_docker as docker
import utils.cloudflare
import utils.docker
import utils.k8s

from monitoring.adguard_exporter import AdGuardExporter
from monitoring.alloy import Alloy
from monitoring.alloy_legacy import AlloyLegacy
from monitoring.cadvisor_legacy import CAdvisorLegacy
from monitoring.config import ComponentConfig
from monitoring.goldilocks import Goldilocks
from monitoring.grafana import Grafana
from monitoring.mimir import Mimir
from monitoring.mimir_buckets import MimirBuckets
from monitoring.node_exporter import create_node_exporter
from monitoring.prometheus_operator_crds import create_prometheus_operator_crds
from monitoring.speedtest import SpeedtestExporter


def main():
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    cloudflare_provider = utils.cloudflare.get_provider(component_config.cloudflare)

    # Buckets for mimir
    mimir_buckets = MimirBuckets('default')

    # Services on synology
    docker_provider = utils.docker.get_provider(component_config.target)
    docker_opts = p.ResourceOptions(provider=docker_provider)

    network = docker.Network('monitoring', opts=docker_opts)

    # Create node-exporter container
    CAdvisorLegacy('default', component_config, network, docker_provider)
    AlloyLegacy('default', component_config, cloudflare_provider, docker_provider)

    # Kubernetes based services
    k8s_provider = utils.k8s.get_k8s_provider()
    Mimir(
        'default',
        component_config,
        cloudflare_provider,
        mimir_buckets,
        k8s_provider,
    )
    Alloy('default', component_config, k8s_provider)
    Grafana('default', component_config, k8s_provider)
    Goldilocks('default', component_config, k8s_provider)
    SpeedtestExporter('default', component_config, k8s_provider)
    AdGuardExporter('default', component_config, k8s_provider)
    create_node_exporter(component_config, k8s_provider)
    create_prometheus_operator_crds(component_config, k8s_provider)
