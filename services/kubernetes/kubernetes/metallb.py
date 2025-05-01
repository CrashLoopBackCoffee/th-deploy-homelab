import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_metallb(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    namespace = k8s.core.v1.Namespace(
        'metallb-system',
        metadata={'name': 'metallb-system'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'metallb-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Note we use Release instead of Chart in order to have one resource instead of 25
    chart = k8s.helm.v3.Release(
        'metallb',
        chart='metallb',
        version=component_config.microk8s.metallb.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://metallb.github.io/metallb'},
        values={
            'prometheus': {
                'rbacPrometheus': False,
                'scrapeAnnotations': True,
            },
        },
        opts=k8s_opts,
    )

    # Create IPAddressPool
    k8s.apiextensions.CustomResource(
        'default-addresspool',
        api_version='metallb.io/v1beta1',
        kind='IPAddressPool',
        metadata={'name': 'default-addresspool'},
        spec={
            'addresses': [
                f'{component_config.microk8s.metallb.start}-{component_config.microk8s.metallb.end}',
            ],
            'autoAssign': True,
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[chart])),
    )

    k8s.apiextensions.CustomResource(
        'l2-advertissment',
        api_version='metallb.io/v1beta1',
        kind='L2Advertisement',
        metadata={'name': 'default-advertise-all-pools'},
        opts=k8s_opts,
    )
