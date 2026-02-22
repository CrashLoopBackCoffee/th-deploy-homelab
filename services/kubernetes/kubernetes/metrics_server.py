import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_metrics_server(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    namespace = k8s.core.v1.Namespace(
        'metrics-server',
        metadata={
            'name': 'metrics-server',
            'labels': {'goldilocks.fairwinds.com/enabled': 'true'},
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'metrics-server-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Note we use Release instead of Chart in order to have one resource instead of many
    k8s.helm.v3.Release(
        'metrics-server',
        chart='metrics-server',
        version=component_config.metrics_server.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://kubernetes-sigs.github.io/metrics-server/'},
        values={
            'args': [
                # MicroK8s uses self-signed certificates for the kubelet, so we need to skip TLS
                # verification
                '--kubelet-insecure-tls',
            ],
        },
        opts=k8s_opts,
    )
