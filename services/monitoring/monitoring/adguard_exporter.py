import pulumi as p
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig

ADGUARD_EXPORTER_PORT = 9618


class AdGuardExporter(p.ComponentResource):
    def __init__(self, name: str, component_config: ComponentConfig, k8s_provider: k8s.Provider):
        """
        Deploys the adguard-exporter
        """
        super().__init__(f'lab:adguard_exporter:{name}', name)

        k8s_opts = p.ResourceOptions(
            provider=k8s_provider,
            parent=self,
        )
        namespace = k8s.core.v1.Namespace(
            'adguard-exporter',
            metadata={
                'name': 'adguard-exporter',
            },
            opts=k8s_opts,
        )

        # Create secret for credentials
        credentials_secret = k8s.core.v1.Secret(
            'adguard-credentials',
            metadata={
                'namespace': namespace.metadata.name,
            },
            string_data={
                'username': component_config.adguard_exporter.username.value,
                'password': component_config.adguard_exporter.password.value,
            },
            opts=k8s_opts,
        )

        app_labels = {'app': 'adguard-exporter'}
        deployment = k8s.apps.v1.Deployment(
            'adguard-exporter',
            metadata={
                'namespace': namespace.metadata.name,
                'name': 'adguard-exporter',
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
                                'name': 'adguard-exporter',
                                'image': f'ghcr.io/henrywhitaker3/adguard-exporter:v{component_config.adguard_exporter.version}',
                                'ports': [
                                    {
                                        'container_port': ADGUARD_EXPORTER_PORT,
                                    },
                                ],
                                'env': [
                                    {
                                        'name': 'ADGUARD_SERVERS',
                                        'value': component_config.adguard_exporter.server,
                                    },
                                    {
                                        'name': 'ADGUARD_USERNAMES',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': credentials_secret.metadata.name,
                                                'key': 'username',
                                            },
                                        },
                                    },
                                    {
                                        'name': 'ADGUARD_PASSWORDS',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': credentials_secret.metadata.name,
                                                'key': 'password',
                                            },
                                        },
                                    },
                                ],
                            },
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        k8s.core.v1.Service(
            'adguard-exporter',
            metadata={
                'namespace': namespace.metadata.name,
                'name': 'adguard-exporter',
                'annotations': {
                    'prometheus.io/scrape': 'true',
                    'prometheus.io/port': str(ADGUARD_EXPORTER_PORT),
                },
            },
            spec={
                'selector': deployment.spec.selector.match_labels,
                'ports': [
                    {
                        'name': 'metrics-adguard',
                        'port': ADGUARD_EXPORTER_PORT,
                        'target_port': ADGUARD_EXPORTER_PORT,
                    },
                ],
            },
            opts=k8s_opts,
        )
