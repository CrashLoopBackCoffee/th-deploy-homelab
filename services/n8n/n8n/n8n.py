import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.opnsense.unbound.host_override

from n8n.config import ComponentConfig

N8N_PORT = 5678


def create_n8n(component_config: ComponentConfig, k8s_provider: k8s.Provider) -> None:
    """
    Deploy n8n workflow automation tool
    """
    assert component_config.n8n

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'n8n',
        metadata={
            'name': 'n8n',
        },
        opts=k8s_opts,
    )

    # Keep using the base provider options for resources

    # Create random encryption key for n8n
    encryption_key = random.RandomPassword(
        'n8n-encryption-key',
        length=32,
        special=True,
        upper=True,
        lower=True,
        numeric=True,
    )

    # Create Kubernetes secret for sensitive data
    secret = k8s.core.v1.Secret(
        'n8n-secret',
        metadata={
            'namespace': namespace.metadata.name,
        },
        type='Opaque',
        string_data={
            'encryption-key': encryption_key.result,
        },
        opts=k8s_opts,
    )

    # Persistent volume claim for n8n data
    pvc = k8s.core.v1.PersistentVolumeClaim(
        'n8n-data',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'n8n-data',
        },
        spec={
            'access_modes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': '5Gi'}},
        },
        opts=k8s_opts,
    )

    app_labels = {'app': 'n8n'}
    deployment = k8s.apps.v1.Deployment(
        'n8n',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'n8n',
        },
        spec={
            'replicas': 1,
            'strategy': {
                'type': 'RollingUpdate',
                'rolling_update': {'max_unavailable': 1, 'max_surge': 0},
            },
            'selector': {'match_labels': app_labels},
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'containers': [
                        {
                            'name': 'n8n',
                            'image': f'n8nio/n8n:{component_config.n8n.version}',
                            'ports': [{'name': 'n8n', 'container_port': N8N_PORT}],
                            'env': [
                                {'name': 'N8N_HOST', 'value': component_config.n8n.hostname},
                                {'name': 'N8N_PORT', 'value': str(N8N_PORT)},
                                {'name': 'N8N_PROTOCOL', 'value': 'https'},
                                {'name': 'NODE_ENV', 'value': 'production'},
                                {'name': 'WEBHOOK_URL', 'value': component_config.n8n.webhook_url},
                                {
                                    'name': 'N8N_ENCRYPTION_KEY',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': secret.metadata.name,
                                            'key': 'encryption-key',
                                        }
                                    },
                                },
                                {'name': 'GENERIC_TIMEZONE', 'value': 'Europe/Berlin'},
                                {'name': 'N8N_DIAGNOSTICS_ENABLED', 'value': 'false'},
                                {'name': 'N8N_PERSONALIZATION_ENABLED', 'value': 'false'},
                                {'name': 'DB_SQLITE_POOL_SIZE', 'value': '10'},
                                {'name': 'N8N_RUNNERS_ENABLED', 'value': 'true'},
                                {'name': 'N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS', 'value': 'true'},
                            ],
                            'security_context': {
                                'run_as_non_root': True,
                                'run_as_user': 1000,
                            },
                            'volume_mounts': [
                                {
                                    'name': 'n8n-data',
                                    'mount_path': '/home/node/.n8n',
                                },
                            ],
                            'resources': component_config.n8n.resources.to_resource_requirements(),
                            'readiness_probe': {
                                'http_get': {
                                    'path': '/healthz',
                                    'port': N8N_PORT,
                                },
                                'period_seconds': 30,
                                'initial_delay_seconds': 30,
                            },
                        },
                    ],
                    'volumes': [
                        {
                            'name': 'n8n-data',
                            'persistent_volume_claim': {
                                'claim_name': pvc.metadata.name,
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    service = k8s.core.v1.Service(
        'n8n',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'n8n',
        },
        spec={
            'ports': [{'name': 'n8n', 'port': N8N_PORT}],
            'selector': deployment.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )

    # Create local DNS record
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'n8n',
        host='n8n',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # Create IngressRoute for internal access
    fqdn = f'n8n.{component_config.cloudflare.zone}'
    k8s.apiextensions.CustomResource(
        'ingress',
        api_version='traefik.io/v1alpha1',
        kind='IngressRoute',
        metadata={
            'name': 'ingress',
            'namespace': namespace.metadata.name,
        },
        spec={
            'entryPoints': ['websecure'],
            'routes': [
                {
                    'kind': 'Rule',
                    'match': p.Output.concat('Host(`', fqdn, '`)'),
                    'services': [
                        {
                            'name': service.metadata.name,
                            'namespace': service.metadata.namespace,
                            'port': N8N_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    p.export(
        'n8n_url',
        p.Output.format('https://{}.{}', record.host, record.domain),
    )

    p.export(
        'n8n_encryption_key',
        encryption_key.result,
    )
