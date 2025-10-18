import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random as random

import utils.opnsense.unbound.host_override

from immich.config import ComponentConfig

IMMICH_PORT = 2283
REDIS_PORT = 6379


def create_immich(
    component_config: ComponentConfig,
    namespace: p.Input[str],
    k8s_provider: k8s.Provider,
    postgres_provider: postgresql.Provider,
    postgres_service: p.Input[str],
    postgres_port: p.Input[int],
):
    """
    Deploy Immich photo management service
    """
    assert component_config.immich

    # Configure database
    postgres_opts = p.ResourceOptions(provider=postgres_provider)
    postgres_password = random.RandomPassword(
        'immich-password',
        length=24,
    )
    postgres_user = postgresql.Role(
        'immich',
        login=True,
        password=postgres_password.result,
        opts=postgres_opts,
    )
    database = postgresql.Database(
        'immich',
        encoding='UTF8',
        lc_collate='C',
        lc_ctype='C',
        owner=postgres_user.name,
        opts=postgres_opts,
    )

    namespaced_provider = k8s.Provider(
        'immich-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace,
    )
    k8s_opts = p.ResourceOptions(
        provider=namespaced_provider,
    )

    # Create Redis
    redis_service = create_redis(component_config, k8s_opts)

    app_labels = {'app': 'immich'}
    sts = k8s.apps.v1.StatefulSet(
        'immich',
        metadata={'name': 'immich'},
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
                                    'value': postgres_service,
                                },
                                {
                                    'name': 'DB_PORT',
                                    'value': p.Output.from_input(postgres_port).apply(
                                        lambda port: str(port)
                                    ),
                                },
                                {
                                    'name': 'DB_DATABASE_NAME',
                                    'value': database.name,
                                },
                                {
                                    'name': 'DB_USERNAME',
                                    'value': postgres_user.name,
                                },
                                {
                                    'name': 'DB_PASSWORD',
                                    'value': postgres_password.result,
                                },
                                {
                                    'name': 'REDIS_HOSTNAME',
                                    'value': redis_service.metadata.name,
                                },
                                {
                                    'name': 'REDIS_PORT',
                                    'value': str(REDIS_PORT),
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
        metadata={'name': 'immich'},
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


def create_redis(component_config: ComponentConfig, opts: p.ResourceOptions) -> k8s.core.v1.Service:
    app_labels_redis = {'app': 'redis'}
    redis_sts = k8s.apps.v1.StatefulSet(
        'redis',
        metadata={'name': 'redis'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_redis},
            'service_name': 'redis-headless',
            'template': {
                'metadata': {'labels': app_labels_redis},
                'spec': {
                    'containers': [
                        {
                            'name': 'redis',
                            'image': f'docker.io/library/redis:{component_config.redis.version}',
                            'ports': [{'container_port': REDIS_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'redis',
        metadata={'name': 'redis'},
        spec={
            'ports': [{'port': REDIS_PORT}],
            'selector': redis_sts.spec.selector.match_labels,
        },
        opts=opts,
    )
