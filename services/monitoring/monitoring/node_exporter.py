import pulumi as p
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig


def create_node_exporter(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy node-exporter on each Kubernetes node.
    """
    namespace = k8s.core.v1.Namespace(
        'node-exporter',
        metadata={
            'name': 'node-exporter',
            'labels': {'goldilocks.fairwinds.com/enabled': 'true'},
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    k8s.helm.v4.Chart(
        'node-exporter',
        chart='prometheus-node-exporter',
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://prometheus-community.github.io/helm-charts'},
        values={
            'image': {
                'tag': f'v{component_config.node_exporter.version}',
            },
            'service': {
                'enabled': False,
            },
            'podAnnotations': {
                'prometheus.io/scrape': 'true',
                'prometheus.io/port': '9100',
            },
        },
        opts=p.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
    )
