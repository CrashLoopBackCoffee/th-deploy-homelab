import typing as t

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

import utils
import utils.port_forward


def _deep_merge(base: dict, overrides: dict) -> dict:
    """Deep merge overrides dict into base dict.

    Args:
        base: Base dictionary.
        overrides: Dictionary with values to override.

    Returns:
        Merged dictionary with overrides applied recursively.
    """
    result = base.copy()
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _create_scheduled_backup(
    cluster_name: str,
    namespace_name: p.Input[str],
    cron_schedule: str,
    k8s_provider: k8s.Provider,
):
    """Create a ScheduledBackup resource for automated daily backups.

    Args:
        cluster_name: Name of the PostgreSQL cluster.
        namespace_name: Kubernetes namespace for deployment.
        cron_schedule: Cron schedule for backups (e.g., '0 0 0 * * *' for daily at midnight UTC).
        k8s_provider: Kubernetes provider instance.

    Returns:
        ScheduledBackup CustomResource.
    """
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    k8s.apiextensions.CustomResource(
        f'{cluster_name}-scheduled-backup',
        api_version='postgresql.cnpg.io/v1',
        kind='ScheduledBackup',
        metadata={
            'name': f'{cluster_name}-daily',
            'namespace': namespace_name,
        },
        spec={
            'schedule': cron_schedule,
            'backupOwnerReference': 'cluster',
            'cluster': {
                'name': cluster_name,
            },
            'method': 'plugin',
            'pluginConfiguration': {
                'name': 'barman-cloud.cloudnative-pg.io',
            },
        },
        opts=k8s_opts,
    )


def _create_backup_objectstore(
    namespace_name: p.Input[str],
    cluster_name: p.Input[str],
    k8s_opts: p.ResourceOptions,
) -> k8s.apiextensions.CustomResource:
    """Create ObjectStore for Barman Cloud Plugin to use IDrive e2 S3 storage."""

    backup_config = p.Config().require_object('postgres-backup')

    # Create secret for S3 credentials
    backup_secret = k8s.core.v1.Secret(
        'postgres-backup-credentials',
        metadata={
            'namespace': namespace_name,
        },
        string_data={
            'access-key-id': backup_config['access-key-id'],
            'secret-access-key': backup_config['secret-access-key'],
        },
        opts=k8s_opts,
    )

    # Create ObjectStore resource for Barman Cloud Plugin
    return k8s.apiextensions.CustomResource(
        'idrive-e2-store',
        api_version='barmancloud.cnpg.io/v1',
        kind='ObjectStore',
        metadata={
            'namespace': namespace_name,
        },
        spec={
            'configuration': {
                'destinationPath': p.Output.concat(
                    backup_config['destination-path'], '/', namespace_name, '/', cluster_name
                ),
                'endpointURL': backup_config['endpoint-url'],
                's3Credentials': {
                    'accessKeyId': {
                        'name': backup_secret.metadata.name,
                        'key': 'access-key-id',
                    },
                    'secretAccessKey': {
                        'name': backup_secret.metadata.name,
                        'key': 'secret-access-key',
                    },
                },
                'wal': {
                    'compression': 'gzip',
                },
            },
        },
        opts=k8s_opts,
    )


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
        enable_superuser: bool = False,
        backup_enabled: bool = False,
        backup_cron: str | None = None,
        backup_config: t.Any | None = None,
        spec_overrides: dict | None = None,
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
            enable_superuser: Whether to enable superuser access (default: False).
            backup_enabled: Whether to enable automated backups (default: False).
            backup_cron: Cron schedule for backups (default: None, uses config default).
            backup_config: BackupConfig object with endpoint and bucket info.
            spec_overrides: Optional dict to override values in the cluster spec (deep merged).
            opts: Pulumi resource options.
        """
        super().__init__(f'lab:postgres:{name}', name, None, opts)

        k8s_opts = p.ResourceOptions(provider=k8s_provider, parent=self)

        # Use component name as cluster name to support multiple instances
        cluster_name = name

        # Build the default spec configuration
        spec = {
            'instances': 1,
            'imageName': f'ghcr.io/cloudnative-pg/postgresql:{version}-minimal-trixie',
            'enableSuperuserAccess': enable_superuser,
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
        }

        # Add backup configuration if enabled
        if backup_enabled and backup_config is not None:
            object_store = _create_backup_objectstore(namespace_name, cluster_name, k8s_opts)
            spec['plugins'] = [
                {
                    'name': 'barman-cloud.cloudnative-pg.io',
                    'isWALArchiver': True,
                    'parameters': {
                        'barmanObjectName': object_store.metadata.apply(lambda m: m['name']),  # pyright: ignore[reportAttributeAccessIssue]
                    },
                }
            ]

        # Apply spec overrides if provided
        if spec_overrides:
            spec = _deep_merge(spec, spec_overrides)

        # Create PostgreSQL cluster using CloudNativePG
        cluster = k8s.apiextensions.CustomResource(
            cluster_name,
            api_version='postgresql.cnpg.io/v1',
            kind='Cluster',
            metadata={
                'name': cluster_name,
                'namespace': namespace_name,
                'annotations': {
                    # Wait for the cluster to be ready
                    'pulumi.com/waitFor': 'condition=Ready',
                },
            },
            spec=spec,
            opts=k8s_opts,
        )

        # Create ScheduledBackup if backup is enabled
        if backup_enabled and backup_config is not None:
            cron = backup_cron or backup_config.cron_schedule
            _create_scheduled_backup(cluster_name, namespace_name, cron, k8s_provider)

        # Retrieve the postgres password from the Kubernetes secret created by CloudNativePG
        # CloudNativePG creates a secret named '{cluster_name}-app' with the password
        # Derive the secret name from cluster metadata to ensure data-driven dependency
        self.secret_name = cluster.metadata.apply(lambda _: f'{cluster_name}-app')  # pyright: ignore[reportAttributeAccessIssue]

        if enable_superuser:
            self.superuser_secret_name = cluster.metadata.apply(  # pyright: ignore[reportAttributeAccessIssue]
                lambda _: f'{cluster_name}-superuser'
            )
        else:
            self.superuser_secret_name = None

        self.register_outputs({})


def create_postgres(
    version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL instance using Bitnami Helm chart.

    .. deprecated::
        Use :class:`PostgresDatabase` component resource instead for proper resource management.
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
