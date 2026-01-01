import pulumi as p
import pulumi_docker as docker
import utils.cloudflare
import utils.docker
import utils.k8s

from monitoring.alloy import Alloy
from monitoring.alloy_legacy import create_alloy_legacy
from monitoring.cadvisor_legacy import create_cadvisor_legacy
from monitoring.config import ComponentConfig
from monitoring.grafana import Grafana
from monitoring.mimir_buckets import MimirBuckets
from monitoring.mimir_legacy import create_mimir_legacy
from monitoring.prometheus_operator_crds import create_prometheus_operator_crds
from monitoring.speedtest import create_speedtest_exporter


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
    create_cadvisor_legacy(component_config, network, docker_opts)
    create_alloy_legacy(component_config, network, cloudflare_provider, docker_opts)
    create_mimir_legacy(component_config, network, cloudflare_provider, mimir_buckets, docker_opts)

    # Kubernetes based services
    k8s_provider = utils.k8s.get_k8s_provider()
    create_prometheus_operator_crds(component_config, k8s_provider)
    Alloy('default', component_config, k8s_provider)
    Grafana('default', component_config, k8s_provider)
    create_speedtest_exporter(component_config, k8s_provider)
