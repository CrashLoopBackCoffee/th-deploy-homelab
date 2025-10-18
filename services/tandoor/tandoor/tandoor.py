import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random as random
import utils.opnsense.unbound.host_override
import utils.postgres

from tandoor.config import ComponentConfig

TANDOOR_PORT = 8080


def create_tandoor(component_config: ComponentConfig, k8s_provider: k8s.Provider) -> None:
    """
    Deploy Tandoor Recipes application
    """
    assert component_config.tandoor

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'tandoor',
        metadata={
            'name': 'tandoor',
        },
        opts=k8s_opts,
    )

    # Create postgres database
    postgres_provider, postgres_service, postgres_port = utils.postgres.create_postgres(
        component_config.postgres.version,
        namespace.metadata.name,
        k8s_provider,
    )

    # Configure database
    postgres_opts = p.ResourceOptions(provider=postgres_provider)
    postgres_password = random.RandomPassword(
        'tandoor-password',
        length=24,
    )
    postgres_user = postgresql.Role(
        'tandoor',
        login=True,
        password=postgres_password.result,
        opts=postgres_opts,
    )
    database = postgresql.Database(
        'tandoor',
        encoding='UTF8',
        lc_collate='en_US.UTF-8',
        lc_ctype='en_US.UTF-8',
        owner=postgres_user.name,
        opts=postgres_opts,
    )

    # Create secret key for Django
    secret_key = random.RandomPassword(
        'tandoor-secret-key',
        length=50,
        special=True,
        upper=True,
        lower=True,
        numeric=True,
    )

    # Create Kubernetes secret for sensitive data
    secret = k8s.core.v1.Secret(
        'tandoor-secret',
        metadata={
            'namespace': namespace.metadata.name,
        },
        type='Opaque',
        string_data={
            'secret-key': secret_key.result,
            'postgres-password': postgres_password.result,
        },
        opts=k8s_opts,
    )

    app_labels = {'app': 'tandoor'}

    # Create StatefulSet with persistent volumes
    sts = k8s.apps.v1.StatefulSet(
        'tandoor',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'tandoor',
        },
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels},
            'service_name': 'tandoor-headless',
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'containers': [
                        {
                            'name': 'tandoor',
                            'image': f'vabene1111/recipes:{component_config.tandoor.version}',
                            'ports': [{'name': 'http', 'container_port': TANDOOR_PORT}],
                            'env': [
                                {
                                    'name': 'SECRET_KEY',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': secret.metadata.name,
                                            'key': 'secret-key',
                                        }
                                    },
                                },
                                {
                                    'name': 'DB_ENGINE',
                                    'value': 'django.db.backends.postgresql',
                                },
                                {
                                    'name': 'POSTGRES_HOST',
                                    'value': postgres_service,
                                },
                                {
                                    'name': 'POSTGRES_PORT',
                                    'value': p.Output.from_input(postgres_port).apply(
                                        lambda port: str(port)
                                    ),
                                },
                                {
                                    'name': 'POSTGRES_DB',
                                    'value': database.name,
                                },
                                {
                                    'name': 'POSTGRES_USER',
                                    'value': postgres_user.name,
                                },
                                {
                                    'name': 'POSTGRES_PASSWORD',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': secret.metadata.name,
                                            'key': 'postgres-password',
                                        }
                                    },
                                },
                                {
                                    'name': 'ALLOWED_HOSTS',
                                    'value': component_config.tandoor.hostname,
                                },
                                {
                                    'name': 'TIMEZONE',
                                    'value': 'Europe/Berlin',
                                },
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'staticfiles',
                                    'mount_path': '/opt/recipes/staticfiles',
                                },
                                {
                                    'name': 'mediafiles',
                                    'mount_path': '/opt/recipes/mediafiles',
                                },
                            ],
                        },
                    ],
                },
            },
            'volume_claim_templates': [
                {
                    'metadata': {'name': 'staticfiles'},
                    'spec': {
                        'access_modes': ['ReadWriteOnce'],
                        'resources': {'requests': {'storage': '5Gi'}},
                    },
                },
                {
                    'metadata': {'name': 'mediafiles'},
                    'spec': {
                        'access_modes': ['ReadWriteOnce'],
                        'resources': {'requests': {'storage': '10Gi'}},
                    },
                },
            ],
        },
        opts=k8s_opts,
    )

    # Create Service
    service = k8s.core.v1.Service(
        'tandoor',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'tandoor',
        },
        spec={
            'ports': [{'name': 'http', 'port': TANDOOR_PORT}],
            'selector': sts.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )

    # Create local DNS record
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'tandoor',
        host='tandoor',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # Create IngressRoute for internal access
    fqdn = f'tandoor.{component_config.cloudflare.zone}'
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
                            'port': TANDOOR_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    p.export(
        'tandoor_url',
        p.Output.format('https://{}.{}', record.host, record.domain),
    )
