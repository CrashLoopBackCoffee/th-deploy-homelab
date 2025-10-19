import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

import utils
import utils.port_forward


class PostgresDatabase(p.ComponentResource):
    def __init__(
        self,
        name: str,
        version: str,
        namespace_name: p.Input[str],
        k8s_provider: k8s.Provider,
        *,
        local_port: int = 15432,
        storage_size: str = '20Gi',
        storage_class: str = 'microk8s-hostpath',
        opts: p.ResourceOptions | None = None,
    ):
        """Initialize PostgreSQL component.

        Args:
            name: Logical name of the component.
            version: PostgreSQL version to deploy.
            namespace_name: Kubernetes namespace for deployment.
            k8s_provider: Kubernetes provider instance.
            local_port: Local port for port forwarding (default: 15432).
            storage_size: Storage size for CloudNativePG backend (default: '20Gi').
            storage_class: Storage class for CloudNativePG backend (default: 'microk8s-hostpath').
            opts: Pulumi resource options.
        """
        super().__init__(f'lab:postgres:{name}', name, None, opts)

        k8s_opts = p.ResourceOptions(provider=k8s_provider, parent=self)

        # Generate secure password for PostgreSQL
        root_password = pulumi_random.RandomPassword(
            'postgres-password',
            length=24,
            special=True,
            opts=p.ResourceOptions(parent=self),
        )

        # Create secret for PostgreSQL credentials
        credentials_secret = k8s.core.v1.Secret(
            'postgres-credentials',
            metadata={
                'namespace': namespace_name,
            },
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
                'imageName': f'ghcr.io/cloudnative-pg/postgresql:{version}-minimal-trixie',
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
            opts=k8s_opts,
        )

        # Introduce a data driven dependency on the cluster creation
        postgres_service = cluster.metadata.apply(lambda _: 'postgres-rw')  # type: ignore[union-attr]

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
        self.postgres_provider = postgresql.Provider(
            'postgres',
            host='localhost',
            port=postgres_port,
            sslmode='disable',
            username='postgres',
            password=root_password.result,
            opts=p.ResourceOptions(parent=self),
        )

        self.service_name = p.Output.from_input(postgres_service)
        self.port = 5432

        self.register_outputs({})


def create_postgres(
    version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL instance using Bitnami Helm chart.

    .. deprecated::
        Use :class:`PostgreSQL` component resource instead for proper resource management.

    Args:
        version: PostgreSQL version to deploy.
        namespace_name: Kubernetes namespace for deployment.
        k8s_provider: Kubernetes provider instance.
        local_port: Local port for port forwarding (default: 15432).

    Returns:
        Tuple of (PostgreSQL provider, service name output, target port).
    """
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
