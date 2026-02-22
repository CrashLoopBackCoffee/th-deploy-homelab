import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.unbound.host_override

from ollama.config import ComponentConfig

OLLAMA_PORT = 11434


def create_ollama(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy Ollama
    """
    assert component_config.ollama

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'ollama',
        metadata={
            'name': 'ollama',
        },
        opts=k8s_opts,
    )

    # Ollama doesn't support PRELOAD_MODELS env var, models need to be pulled manually
    env_vars = []

    app_labels = {'app': 'ollama'}
    sts = k8s.apps.v1.StatefulSet(
        'ollama',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'ollama',
        },
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels},
            'service_name': 'ollama-headless',
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'containers': [
                        {
                            'name': 'ollama',
                            'image': f'ollama/ollama:{component_config.ollama.version}',
                            'ports': [{'container_port': OLLAMA_PORT}],
                            'env': env_vars,
                            'volume_mounts': [
                                {
                                    'name': 'ollama-data',
                                    'mount_path': '/root/.ollama',
                                },
                            ],
                            'resources': component_config.ollama.resources.to_resource_requirements(),
                            'readiness_probe': {
                                'http_get': {
                                    'path': '/',
                                    'port': OLLAMA_PORT,
                                },
                                'period_seconds': 10,
                            },
                        },
                    ],
                },
            },
            'volume_claim_templates': [
                {
                    'metadata': {'name': 'ollama-data'},
                    'spec': {
                        'access_modes': ['ReadWriteOnce'],
                        'resources': {'requests': {'storage': '20Gi'}},
                    },
                },
            ],
        },
        opts=k8s_opts,
    )

    service = k8s.core.v1.Service(
        'ollama',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'ollama',
        },
        spec={
            'ports': [{'port': OLLAMA_PORT}],
            'selector': sts.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )

    # Create local DNS record
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'ollama',
        host='ollama',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # Create IngressRoute for internal access
    fqdn = f'ollama.{component_config.cloudflare.zone}'
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
                            'port': OLLAMA_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    p.export(
        'ollama_url',
        p.Output.format('https://{}.{}', record.host, record.domain),
    )
