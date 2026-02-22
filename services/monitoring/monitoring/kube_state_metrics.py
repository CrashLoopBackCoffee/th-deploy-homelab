import pulumi as p
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig


def create_kube_state_metrics(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy kube-state-metrics to expose Kubernetes cluster state as Prometheus metrics.
    """
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    namespace = k8s.core.v1.Namespace(
        'kube-state-metrics',
        metadata={'name': 'kube-state-metrics'},
        opts=k8s_opts,
    )

    k8s.helm.v4.Chart(
        'kube-state-metrics',
        chart='kube-state-metrics',
        version=component_config.kube_state_metrics.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://prometheus-community.github.io/helm-charts'},
        values={
            'resources': component_config.kube_state_metrics.resources.to_resource_requirements(),
        },
        opts=p.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
    )
