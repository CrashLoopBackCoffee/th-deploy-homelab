import pulumi as p
import pulumi_kubernetes as k8s

import utils.opnsense.unbound.host_override

from immich.config import ComponentConfig

IMMICH_PORT = 2283


def create_immich(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy Immich photo management service
    """
    assert component_config.immich

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'immich',
        metadata={
            'name': 'immich',
        },
        opts=k8s_opts,
    )

    app_labels = {'app': 'immich'}
    sts = k8s.apps.v1.StatefulSet(
        'immich',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'immich',
        },
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels},
            'service_name': 'immich-headless',
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'containers': [
                        {
                            'name': 'immich',
                            'image': f'ghcr.io/immich-app/immich-server:{component_config.immich.version}',
                            'ports': [{'container_port': IMMICH_PORT}],
                            'env': [
                                {
                                    'name': 'DB_HOSTNAME',
                                    'value': 'immich-postgres',
                                },
                                {
                                    'name': 'DB_DATABASE_NAME',
                                    'value': 'immich',
                                },
                                {
                                    'name': 'DB_USERNAME',
                                    'value': 'postgres',
                                },
                                {
                                    'name': 'DB_PASSWORD',
                                    'value': 'postgres',
                                },
                                {
                                    'name': 'REDIS_HOSTNAME',
                                    'value': 'immich-redis',
                                },
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'library',
                                    'mount_path': '/usr/src/app/upload',
                                },
                            ],
                        },
                    ],
                    'volumes': [
                        {
                            'name': 'library',
                            'csi': {
                                'driver': 'nfs.csi.k8s.io',
                                'volume_attributes': {
                                    'server': component_config.immich.library_server,
                                    'share': component_config.immich.library_share,
                                    'mount_options': component_config.immich.library_mount_options,
                                },
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    service = k8s.core.v1.Service(
        'immich',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'immich',
        },
        spec={
            'ports': [{'port': IMMICH_PORT}],
            'selector': sts.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )

    # Create local DNS record
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'immich',
        host='immich',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # Create IngressRoute for internal access
    fqdn = f'immich.{component_config.cloudflare.zone}'
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
                            'port': IMMICH_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    p.export(
        'immich_url',
        p.Output.format('https://{}.{}', record.host, record.domain),
    )
