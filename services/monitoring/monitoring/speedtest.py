import pulumi as p
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig

SPEEDTEST_EXPORTER_PORT = 9469


def create_speedtest_exporter(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploys the speedtest-exporter
    """
    assert component_config.speedtest_exporter

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'speedtest-exporter',
        metadata={
            'name': 'speedtest-exporter',
        },
        opts=k8s_opts,
    )

    app_labels = {'app': 'speedtest-exporter'}
    deployment = k8s.apps.v1.Deployment(
        'speedtest-exporter',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'speedtest-exporter',
        },
        spec={
            'selector': {
                'match_labels': app_labels,
            },
            'replicas': 1,
            'template': {
                'metadata': {
                    'labels': app_labels,
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'speedtest-exporter',
                            'image': f'billimek/prometheus-speedtest-exporter:{component_config.speedtest_exporter.version}',
                            'ports': [
                                {
                                    'container_port': SPEEDTEST_EXPORTER_PORT,
                                },
                            ],
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    service = k8s.core.v1.Service(
        'speedtest-exporter',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'speedtest-exporter',
        },
        spec={
            'selector': deployment.spec.selector.match_labels,
            'ports': [
                {
                    'port': SPEEDTEST_EXPORTER_PORT,
                    'target_port': SPEEDTEST_EXPORTER_PORT,
                },
            ],
            'type': 'LoadBalancer',
        },
        opts=k8s_opts,
    )

    p.export(
        'speedtest-exporter',
        p.Output.format(
            'http://{}:{}', service.status.load_balancer.ingress[0].ip, SPEEDTEST_EXPORTER_PORT
        ),
    )
