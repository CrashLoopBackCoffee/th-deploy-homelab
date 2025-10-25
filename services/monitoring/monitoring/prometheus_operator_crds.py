import pulumi as p
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig


def create_prometheus_operator_crds(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy Prometheus Operator CRDs via Helm.
    """
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    k8s.helm.v4.Chart(
        'prometheus-operator-crds',
        chart='prometheus-operator-crds',
        version=component_config.prometheus_operator_crds.version,
        repository_opts={
            'repo': 'https://prometheus-community.github.io/helm-charts',
        },
        opts=k8s_opts,
    )
