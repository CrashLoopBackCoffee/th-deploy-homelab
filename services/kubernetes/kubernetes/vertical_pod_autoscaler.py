import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_vertical_pod_autoscaler(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    k8s.helm.v4.Chart(
        'vertical-pod-autoscaler',
        chart='vertical-pod-autoscaler',
        namespace='kube-system',
        version=component_config.vertical_pod_autoscaler.version,
        repository_opts={'repo': 'https://kubernetes.github.io/autoscaler'},
        values={
            'admissionController': {'enabled': False},
            'recommender': {
                'enabled': True,
                'replicas': 1,
                'affinity': None,
                'extraArgs': ['--pod-recommendation-min-memory-mb=25'],
                'resources': component_config.vertical_pod_autoscaler.resources.to_resource_requirements(),
            },
            'updater': {'enabled': False},
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )
