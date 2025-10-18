import enum

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

import utils
import utils.port_forward


class PostgresBackend(str, enum.Enum):
    """PostgreSQL deployment backend."""

    BITNAMI = 'bitnami'
    CLOUDNATIVE_PG = 'cloudnative-pg'


def create_postgres(
    version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    local_port: int = 15432,
    backend: PostgresBackend = PostgresBackend.CLOUDNATIVE_PG,
    storage_size: str = '20Gi',
    storage_class: str = 'microk8s-hostpath',
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL instance using either Bitnami Helm chart or CloudNativePG operator.

    Args:
        version: PostgreSQL version to deploy.
        namespace_name: Kubernetes namespace for deployment.
        k8s_provider: Kubernetes provider instance.
        local_port: Local port for port forwarding (default: 15432).
        backend: PostgreSQL backend to use - 'bitnami' or 'cloudnative-pg' (default: 'bitnami').
        storage_size: Storage size for CloudNativePG backend (default: '20Gi').
        storage_class: Storage class for CloudNativePG backend (default: 'microk8s-hostpath').

    Returns:
        Tuple of (PostgreSQL provider, service name output, target port).
    """
    if backend == PostgresBackend.CLOUDNATIVE_PG:
        return _create_postgres_cloudnative_pg(
            postgres_version=version,
            namespace_name=namespace_name,
            k8s_provider=k8s_provider,
            storage_size=storage_size,
            storage_class=storage_class,
            local_port=local_port,
        )
    return _create_postgres_bitnami(
        version=version,
        namespace_name=namespace_name,
        k8s_provider=k8s_provider,
        local_port=local_port,
    )


def _create_postgres_bitnami(
    version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL using Bitnami Helm chart."""
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    root_password = pulumi_random.RandomPassword(
        'postgres-password',
        length=24,
    )

    chart = k8s.helm.v3.Release(
        'postgres',
        chart='oci://registry-1.docker.io/bitnamicharts/postgresql',
        version=version,
        namespace=namespace_name,
        values={
            'auth': {
                'postgresPassword': root_password.result,
            },
            # Temporary workaround for Bitnami repository changes (issue #35164)
            # Use bitnamilegacy repository for container images
            'image': {
                'repository': 'bitnamilegacy/postgresql',
            },
            'volumePermissions': {
                'image': {
                    'repository': 'bitnamilegacy/os-shell',
                },
            },
            'metrics': {
                'enabled': True,
                'image': {
                    'repository': 'bitnamilegacy/postgres-exporter',
                },
            },
            'global': {
                'security': {
                    'allowInsecureImages': True,
                },
            },
        },
        opts=k8s_opts,
    )

    postgres_service = chart.resource_names.apply(
        lambda names: [name for name in names['Service/v1'] if name.endswith('postgresql')][0]  # type: ignore
    ).apply(lambda name: name.split('/')[-1])

    postgres_port = utils.port_forward.ensure_port_forward(
        local_port=local_port,
        namespace=namespace_name,
        resource_type=utils.port_forward.ResourceType.SERVICE,
        resource_name=postgres_service,
        target_port='tcp-postgresql',
        k8s_provider=k8s_provider,
    )

    return (
        postgresql.Provider(
            'postgres',
            host='localhost',
            port=postgres_port,
            sslmode='disable',
            password=root_password.result,
        ),
        postgres_service,
        5432,
    )


def _create_postgres_cloudnative_pg(
    postgres_version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    storage_size: str = '20Gi',
    storage_class: str = 'microk8s-hostpath',
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL using CloudNativePG operator."""
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    # Generate secure password for PostgreSQL
    root_password = pulumi_random.RandomPassword(
        'postgres-password-cnpg',
        length=24,
        special=True,
    )

    # Create secret for PostgreSQL credentials
    credentials_secret = k8s.core.v1.Secret(
        'postgres-credentials-cnpg',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres-credentials',
            namespace=namespace_name,
        ),
        string_data={
            'username': 'postgres',
            'password': root_password.result,
        },
        opts=k8s_opts,
    )

    # Create PostgreSQL cluster using CloudNativePG
    cluster = k8s.apiextensions.CustomResource(
        'postgres',
        api_version='postgresql.cnpg.io/v1',
        kind='Cluster',
        metadata={
            'name': 'postgres',
            'namespace': namespace_name,
            'annotations': {
                # Wait for the cluster to be ready
                'pulumi.com/waitFor': 'condition=Ready',
            },
        },
        spec={
            'instances': 1,
            'imageName': f'ghcr.io/cloudnative-pg/postgresql:{postgres_version}-minimal-trixie',
            # PostgreSQL configuration
            'postgresql': {
                'parameters': {
                    # Performance tuning for homelab environment
                    'max_connections': '100',
                    'shared_buffers': '256MB',
                    'effective_cache_size': '1GB',
                    'maintenance_work_mem': '64MB',
                    'checkpoint_completion_target': '0.9',
                    'wal_buffers': '16MB',
                    'default_statistics_target': '100',
                    'random_page_cost': '1.1',
                    'effective_io_concurrency': '200',
                    # Logging configuration
                    'log_min_duration_statement': '1000',
                    'log_line_prefix': '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ',
                    'log_checkpoints': 'on',
                    'log_connections': 'on',
                    'log_disconnections': 'on',
                    'log_lock_waits': 'on',
                }
            },
            # Bootstrap configuration
            'bootstrap': {
                'initdb': {
                    'secret': {
                        'name': credentials_secret.metadata.name,
                    },
                    'options': [
                        '--encoding=UTF8',
                        '--lc-collate=C',
                        '--lc-ctype=C',
                    ],
                }
            },
            # Storage configuration
            'storage': {
                'size': storage_size,
                'storageClass': storage_class,
            },
        },
        opts=p.ResourceOptions(
            provider=k8s_provider,
        ),
    )

    # Introduce a data driven dependency on the cluster creation
    postgres_service = cluster.metadata.apply(lambda _: 'postgres-rw')  # pyright: ignore[reportAttributeAccessIssue]

    # Set up port forwarding for local development/management
    postgres_port = utils.port_forward.ensure_port_forward(
        local_port=local_port,
        namespace=namespace_name,
        resource_type=utils.port_forward.ResourceType.SERVICE,
        resource_name=postgres_service,
        target_port='5432',
        k8s_provider=k8s_provider,
    )

    # Create PostgreSQL provider for database/user management
    postgres_provider = postgresql.Provider(
        'postgres-cnpg',
        host='localhost',
        port=postgres_port,
        sslmode='disable',
        username='postgres',
        password=root_password.result,
    )

    return (
        postgres_provider,
        p.Output.from_input(postgres_service),
        5432,
    )
