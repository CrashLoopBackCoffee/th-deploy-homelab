import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_cloudnative_pg(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """Create CloudNativePG operator for PostgreSQL cluster management."""
    namespace = k8s.core.v1.Namespace(
        'cnpg-system',
        metadata={'name': 'cnpg-system'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'cnpg-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Install CloudNativePG operator using Helm chart
    return k8s.helm.v4.Chart(
        'cloudnative-pg',
        chart='cloudnative-pg',
        version=component_config.cloudnative_pg.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://cloudnative-pg.github.io/charts'},
        values={
            'config': {
                'create': True,
                'secret': False,
            },
        },
        opts=k8s_opts,
    )
