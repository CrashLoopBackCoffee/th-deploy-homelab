"""
Installs acme on synology NAS.

Synology has native support for acme through their DSM interface, but it
doesn't support DNS-01 challenges which requires to forward port 80 to the
NAS. This is not acceptable for security reasons.
"""

import pathlib

import pulumi as p
import pulumi_kubernetes as k8s

from ingress.config import ComponentConfig


class AcmeSynology(p.ComponentResource):
    @staticmethod
    def _hostname_to_secret_name(hostname: str) -> str:
        """Convert hostname to a valid Kubernetes secret name."""
        # Replace * with wildcard, remove dots
        return hostname.replace('*', 'wildcard').replace('.', '-') + '-tls'

    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        k8s_provider: k8s.Provider,
    ):
        super().__init__(
            f'lab:ingress:AcmeSynology:{name}', name, opts=p.ResourceOptions(provider=k8s_provider)
        )

        if not component_config.synology:
            return

        synology_config = component_config.synology

        # Create namespace
        namespace = k8s.core.v1.Namespace(
            'synology-certs-namespace',
            metadata={'name': 'synology-certs'},
            opts=p.ResourceOptions(parent=self, provider=k8s_provider),
        )

        # Read the deployment script
        script_path = pathlib.Path(__file__).parent.parent / 'assets' / 'synology-cert-deploy.sh'
        script_content = script_path.read_text()

        # Create ConfigMap with the deployment script
        script_configmap = k8s.core.v1.ConfigMap(
            'synology-deploy-script',
            metadata={
                'name': 'synology-cert-deploy-script',
                'namespace': namespace.metadata.name,
            },
            data={'synology-cert-deploy.sh': script_content},
            opts=p.ResourceOptions(parent=namespace, provider=k8s_provider),
        )

        # Create Secret with Synology credentials
        credentials_secret = k8s.core.v1.Secret(
            'synology-credentials',
            metadata={
                'name': 'synology-credentials',
                'namespace': namespace.metadata.name,
            },
            string_data={
                'SYNO_HOSTNAME': synology_config.host,
                'SYNO_PORT': str(synology_config.port),
                'SYNO_SCHEME': synology_config.scheme,
                'SYNO_USERNAME': synology_config.username.value,
                'SYNO_PASSWORD': synology_config.password.value,
            },
            opts=p.ResourceOptions(parent=namespace, provider=k8s_provider),
        )

        # Create a CronJob for each certificate
        for cert in synology_config.certs:
            self._create_cert_cronjob(
                cert=cert,
                namespace=namespace,
                script_configmap=script_configmap,
                credentials_secret=credentials_secret,
                k8s_provider=k8s_provider,
            )

    def _create_cert_cronjob(
        self,
        cert,
        namespace: k8s.core.v1.Namespace,
        script_configmap: k8s.core.v1.ConfigMap,
        credentials_secret: k8s.core.v1.Secret,
        k8s_provider: k8s.Provider,
    ):
        """Create a Certificate and CronJob for deploying a single certificate to Synology."""
        # Sanitize hostname for resource name
        sanitized_name = cert.hostname.replace('.', '-').replace('*', 'wildcard')
        secret_name = self._hostname_to_secret_name(cert.hostname)

        # Create cert-manager Certificate resource
        k8s.apiextensions.CustomResource(
            f'cert-{sanitized_name}',
            api_version='cert-manager.io/v1',
            kind='Certificate',
            metadata={
                'name': f'cert-{sanitized_name}',
                'namespace': namespace.metadata.name,
            },
            spec={
                'secretName': secret_name,
                'issuerRef': {
                    'name': 'lets-encrypt',
                    'kind': 'ClusterIssuer',
                },
                'dnsNames': [cert.hostname],
            },
            opts=p.ResourceOptions(parent=namespace, provider=k8s_provider),
        )

        k8s.batch.v1.CronJob(
            f'synology-cert-{sanitized_name}',
            metadata={
                'name': f'synology-cert-{sanitized_name}',
                'namespace': namespace.metadata.name,
            },
            spec={
                # Run daily at 11:55 PM (before Synology nginx reload at midnight)
                'schedule': '55 23 * * *',
                'successful_jobs_history_limit': 3,
                'failed_jobs_history_limit': 3,
                'job_template': {
                    'spec': {
                        'template': {
                            'spec': {
                                'restart_policy': 'OnFailure',
                                'containers': [
                                    {
                                        'name': 'cert-updater',
                                        'image': 'buildpack-deps:bookworm-curl',
                                        'command': [
                                            '/bin/bash',
                                            '/scripts/synology-cert-deploy.sh',
                                        ],
                                        'env': [
                                            {'name': 'CERT_KEY_FILE', 'value': '/certs/tls.key'},
                                            {'name': 'CERT_CERT_FILE', 'value': '/certs/tls.crt'},
                                            {'name': 'SYNO_CERTIFICATE', 'value': cert.hostname},
                                        ],
                                        'env_from': [
                                            {
                                                'secret_ref': {
                                                    'name': credentials_secret.metadata.name,
                                                },
                                            },
                                        ],
                                        'volume_mounts': [
                                            {
                                                'name': 'certs',
                                                'mount_path': '/certs',
                                                'read_only': True,
                                            },
                                            {
                                                'name': 'script',
                                                'mount_path': '/scripts',
                                                'read_only': True,
                                            },
                                        ],
                                    },
                                ],
                                'volumes': [
                                    {
                                        'name': 'certs',
                                        'secret': {
                                            'secret_name': self._hostname_to_secret_name(
                                                cert.hostname
                                            )
                                        },
                                    },
                                    {
                                        'name': 'script',
                                        'config_map': {
                                            'name': script_configmap.metadata.name,
                                            'default_mode': 0o755,
                                        },
                                    },
                                ],
                            },
                        },
                    },
                },
            },
            opts=p.ResourceOptions(parent=namespace, provider=k8s_provider),
        )
