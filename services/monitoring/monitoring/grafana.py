import textwrap

import pulumi as p
import pulumi_kubernetes as k8s
import yaml

from monitoring.config import ComponentConfig

GRAFANA_PORT = 3000


def _get_grafana_config(hostname: str):
    return textwrap.dedent(
        f"""\
        [server]
        http_addr =
        http_port = 3000
        root_url = https://{hostname}
        cert_key = /etc/grafana/certs/tls.key
        cert_file = /etc/grafana/certs/tls.crt
        protocol = https
        """
    )


def create_grafana(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy Grafana
    """
    assert component_config.grafana
    assert component_config.grafana.hostname

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'grafana',
        metadata={
            'name': 'grafana',
        },
        opts=k8s_opts,
    )

    # Create data volume
    pvc = k8s.core.v1.PersistentVolumeClaim(
        'grafana-data',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'grafana-data',
        },
        spec={
            'access_modes': ['ReadWriteOnce'],
            'resources': {
                'requests': {
                    'storage': '1Gi',
                },
            },
        },
        opts=k8s_opts,
    )

    config_datasources = k8s.core.v1.ConfigMap(
        'grafana-datasources',
        metadata={
            'namespace': namespace.metadata.name,
        },
        data={
            'datasources.yml': yaml.safe_dump(
                {
                    'apiVersion': 1,
                    'deleteDatasources': [{'name': 'Prometheus', 'orgId': 1}],
                    'datasources': [
                        {
                            'name': 'Prometheus',
                            'type': 'prometheus',
                            'access': 'proxy',
                            'orgId': 1,
                            'url': 'http://192.168.2.11:9009/prometheus',
                            'basicAuth': False,
                            'isDefault': True,
                            'jsonData': {
                                'httpMethod': 'POST',
                                'prometheusType': 'Mimir',
                                'prometheusVersion': '2.9.1',
                            },
                            'version': 1,
                            'editable': True,
                        },
                    ],
                }
            ),
        },
        opts=k8s_opts,
    )

    # Create TLS certs
    certificate = k8s.apiextensions.CustomResource(
        'certificate',
        api_version='cert-manager.io/v1',
        kind='Certificate',
        metadata={
            'name': 'grafana-tls',
            'namespace': namespace.metadata.name,
            'annotations': {
                # Wait for the certificate to be ready
                'pulumi.com/waitFor': 'condition=Ready',
            },
        },
        spec={
            'secretName': 'grafana-tls',
            'dnsNames': [component_config.grafana.hostname],
            'issuerRef': {'name': 'lets-encrypt', 'kind': 'ClusterIssuer'},
        },
        opts=k8s_opts,
    )

    grafana_config = k8s.core.v1.ConfigMap(
        'grafana-config',
        metadata={
            'namespace': namespace.metadata.name,
        },
        data={'grafana.ini': _get_grafana_config(component_config.grafana.hostname)},
        opts=k8s_opts,
    )

    app_labels = {'app': 'grafana'}
    deployment = k8s.apps.v1.Deployment(
        'grafana',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'grafana',
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
                            'name': 'grafana',
                            'image': f'grafana/grafana:{component_config.grafana.version}',
                            'ports': [
                                {
                                    'container_port': GRAFANA_PORT,
                                },
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'grafana-config',
                                    'mount_path': '/etc/grafana/grafana.ini',
                                    'sub_path': 'grafana.ini',
                                },
                                {
                                    'name': 'grafana-data',
                                    'mount_path': '/var/lib/grafana',
                                },
                                {
                                    'name': 'grafana-datasources',
                                    'mount_path': '/etc/grafana/provisioning/datasources/datasources.yml',
                                    'sub_path': 'datasources.yml',
                                },
                                {
                                    'name': 'grafana-tls',
                                    'mount_path': '/etc/grafana/certs',
                                },
                            ],
                        },
                    ],
                    'readiness_probe': {
                        'failure_threshold': 3,
                        'http_get': {
                            'path': '/robots.txt',
                            'port': GRAFANA_PORT,
                            'scheme': 'HTTPS',
                        },
                    },
                    'security_context': {
                        'fsGroup': 472,
                        'supplemental_groups': [0],
                    },
                    'volumes': [
                        {
                            'name': 'grafana-config',
                            'config_map': {
                                'name': grafana_config.metadata.name,
                            },
                        },
                        {
                            'name': 'grafana-data',
                            'persistent_volume_claim': {
                                'claim_name': pvc.metadata.name,
                            },
                        },
                        {
                            'name': 'grafana-datasources',
                            'config_map': {
                                'name': config_datasources.metadata.name,
                            },
                        },
                        {
                            'name': 'grafana-tls',
                            'secret': {
                                'secret_name': certificate.spec['secretName'],  # type: ignore
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    service = k8s.core.v1.Service(
        'grafana',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'grafana',
        },
        spec={
            'selector': deployment.spec.selector.match_labels,
            'ports': [
                {
                    'port': 443,
                    'target_port': GRAFANA_PORT,
                },
            ],
            'type': 'LoadBalancer',
            'external_traffic_policy': 'Local',
        },
        opts=k8s_opts,
    )

    p.export('grafana-address', service.status.load_balancer.ingress[0].ip)
    p.export('grafana', p.Output.format('https://{}', component_config.grafana.hostname))
