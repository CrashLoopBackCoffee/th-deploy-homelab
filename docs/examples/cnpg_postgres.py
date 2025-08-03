"""
CloudNativePG PostgreSQL deployment for homelab.

This module provides a CloudNativePG-based replacement for the Bitnami PostgreSQL Helm chart.
It creates a PostgreSQL cluster using the CloudNativePG operator with proper configuration
for the homelab environment.
"""

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

import utils
import utils.port_forward


def create_cnpg_postgres(
    postgres_version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    storage_size: str = "20Gi",
    storage_class: str = "local-path",
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """
    Create PostgreSQL cluster using CloudNativePG operator.
    
    Args:
        postgres_version: PostgreSQL version to deploy (e.g., "16")
        namespace_name: Kubernetes namespace for deployment
        k8s_provider: Kubernetes provider instance
        storage_size: Size of persistent storage (default: "20Gi")
        storage_class: Storage class for persistent volumes (default: "local-path")
        local_port: Local port for port forwarding (default: 15432)
        
    Returns:
        Tuple of (PostgreSQL provider, service name, target port)
    """
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    # Generate secure password for PostgreSQL
    root_password = pulumi_random.RandomPassword(
        'postgres-password',
        length=24,
        special=True,
    )

    # Create secret for PostgreSQL credentials
    credentials_secret = k8s.core.v1.Secret(
        'paperless-postgres-credentials',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='paperless-postgres-credentials',
            namespace=namespace_name,
        ),
        string_data={
            'username': 'paperless',
            'password': root_password.result,
        },
        opts=k8s_opts,
    )

    # Create PostgreSQL cluster using CloudNativePG
    cluster = k8s.apiextensions.CustomResource(
        'paperless-postgres',
        api_version='postgresql.cnpg.io/v1',
        kind='Cluster',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='paperless-postgres',
            namespace=namespace_name,
        ),
        spec={
            'instances': 1,
            'imageName': f'postgres:{postgres_version}',
            
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
                    'database': 'paperless',
                    'owner': 'paperless',
                    'secret': {
                        'name': 'paperless-postgres-credentials'
                    },
                    'options': [
                        '--encoding=UTF8',
                        '--lc-collate=C',
                        '--lc-ctype=C'
                    ]
                }
            },
            
            # Storage configuration
            'storage': {
                'size': storage_size,
                'storageClass': storage_class
            },
            
            # Monitoring configuration
            'monitoring': {
                'enabled': True,
                'podMonitorLabels': {
                    'app': 'paperless-postgres'
                }
            },
            
            # Backup configuration (for future use with S3/MinIO)
            'backup': {
                'retentionPolicy': '7d',
                'barmanObjectStore': {
                    's3Credentials': {
                        'accessKeyId': {
                            'name': 'backup-credentials',
                            'key': 'access-key-id'
                        },
                        'secretAccessKey': {
                            'name': 'backup-credentials', 
                            'key': 'secret-access-key'
                        }
                    },
                    'endpointURL': 'https://s3.tobiash.net',
                    'destinationPath': 's3://postgresql-backups/paperless',
                }
            }
        },
        opts=p.ResourceOptions(
            provider=k8s_provider,
            depends_on=[credentials_secret]
        ),
    )

    # Service name follows CloudNativePG naming convention
    # -rw suffix indicates read-write service
    postgres_service = p.Output.concat(cluster.metadata.name, '-rw')

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
        'postgres',
        host='localhost',
        port=postgres_port,
        sslmode='disable',
        username='paperless',
        password=root_password.result,
    )

    return (
        postgres_provider,
        postgres_service,
        5432,
    )


def create_cnpg_operator(
    k8s_provider: k8s.Provider,
    operator_version: str = "1.24.1",
) -> k8s.apiextensions.CustomResource:
    """
    Deploy CloudNativePG operator if not already present.
    
    Args:
        k8s_provider: Kubernetes provider instance
        operator_version: CloudNativePG operator version
        
    Returns:
        CloudNativePG operator deployment
    """
    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    
    # Create namespace for operator
    operator_namespace = k8s.core.v1.Namespace(
        'cnpg-system',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='cnpg-system',
        ),
        opts=k8s_opts,
    )
    
    # Deploy operator using Helm chart
    operator = k8s.helm.v3.Release(
        'cloudnative-pg',
        chart='cloudnative-pg',
        version=operator_version,
        repository_opts=k8s.helm.v3.RepositoryOptsArgs(
            repo='https://cloudnative-pg.github.io/charts'
        ),
        namespace=operator_namespace.metadata.name,
        values={
            'config': {
                'create': True,
                'data': {
                    'INHERITED_ANNOTATIONS': 'prometheus.io/scrape',
                    'INHERITED_LABELS': 'app.kubernetes.io/name',
                }
            },
            'monitoring': {
                'enabled': True,
                'podMonitor': {
                    'enabled': True
                }
            }
        },
        opts=p.ResourceOptions(
            provider=k8s_provider,
            depends_on=[operator_namespace]
        ),
    )
    
    return operator