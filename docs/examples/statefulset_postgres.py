"""
Custom StatefulSet PostgreSQL deployment for homelab.

This module provides a simple StatefulSet-based PostgreSQL deployment as an alternative
to both Bitnami charts and complex operators. It uses official PostgreSQL images and
provides basic functionality with full control over the deployment.
"""

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

import utils
import utils.port_forward


def create_statefulset_postgres(
    postgres_version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    storage_size: str = "20Gi",
    storage_class: str = "local-path",
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """
    Create PostgreSQL using StatefulSet with official PostgreSQL image.
    
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
        'postgres-credentials',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres-credentials',
            namespace=namespace_name,
        ),
        string_data={
            'postgres-password': root_password.result,
            'paperless-password': root_password.result,
        },
        opts=k8s_opts,
    )

    # Create ConfigMap for PostgreSQL configuration
    postgres_config = k8s.core.v1.ConfigMap(
        'postgres-config',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres-config',
            namespace=namespace_name,
        ),
        data={
            'postgresql.conf': '''
# PostgreSQL configuration for homelab
# Performance tuning
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_min_duration_statement = 1000
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on

# Connection settings
listen_addresses = '*'
port = 5432
''',
            'init-paperless-db.sql': '''
-- Initialize Paperless database and user
CREATE DATABASE paperless;
CREATE USER paperless WITH PASSWORD 'PLACEHOLDER_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE paperless TO paperless;
ALTER DATABASE paperless OWNER TO paperless;
'''
        },
        opts=k8s_opts,
    )

    # Create init script to set up Paperless database
    init_script = k8s.core.v1.ConfigMap(
        'postgres-init',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres-init',
            namespace=namespace_name,
        ),
        data={
            'init.sh': p.Output.all(root_password.result).apply(
                lambda args: f'''#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
until pg_isready -h localhost -p 5432 -U postgres; do
    echo "Waiting for PostgreSQL to be ready..."
    sleep 2
done

# Create paperless database and user if they don't exist
psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres <<-EOSQL
    SELECT 'CREATE DATABASE paperless' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'paperless')\\gexec
    DO \\$\\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'paperless') THEN
            CREATE USER paperless WITH PASSWORD '{args[0]}';
        END IF;
    END
    \\$\\$;
    GRANT ALL PRIVILEGES ON DATABASE paperless TO paperless;
    ALTER DATABASE paperless OWNER TO paperless;
EOSQL

echo "Database initialization completed"
'''
            )
        },
        opts=k8s_opts,
    )

    # Create StatefulSet for PostgreSQL
    statefulset = k8s.apps.v1.StatefulSet(
        'postgres',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres',
            namespace=namespace_name,
            labels={'app': 'postgres'}
        ),
        spec=k8s.apps.v1.StatefulSetSpecArgs(
            service_name='postgres',
            replicas=1,
            selector=k8s.meta.v1.LabelSelectorArgs(
                match_labels={'app': 'postgres'}
            ),
            template=k8s.core.v1.PodTemplateSpecArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    labels={'app': 'postgres'}
                ),
                spec=k8s.core.v1.PodSpecArgs(
                    containers=[
                        k8s.core.v1.ContainerArgs(
                            name='postgres',
                            image=f'postgres:{postgres_version}',
                            env=[
                                k8s.core.v1.EnvVarArgs(
                                    name='POSTGRES_DB',
                                    value='postgres'
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name='POSTGRES_USER',
                                    value='postgres'
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name='POSTGRES_PASSWORD',
                                    value_from=k8s.core.v1.EnvVarSourceArgs(
                                        secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                                            name='postgres-credentials',
                                            key='postgres-password'
                                        )
                                    )
                                ),
                                k8s.core.v1.EnvVarArgs(
                                    name='PGDATA',
                                    value='/var/lib/postgresql/data/pgdata'
                                ),
                            ],
                            ports=[k8s.core.v1.ContainerPortArgs(
                                name='postgres',
                                container_port=5432
                            )],
                            volume_mounts=[
                                k8s.core.v1.VolumeMountArgs(
                                    name='postgres-storage',
                                    mount_path='/var/lib/postgresql/data'
                                ),
                                k8s.core.v1.VolumeMountArgs(
                                    name='postgres-config',
                                    mount_path='/etc/postgresql/postgresql.conf',
                                    sub_path='postgresql.conf'
                                ),
                                k8s.core.v1.VolumeMountArgs(
                                    name='postgres-init',
                                    mount_path='/docker-entrypoint-initdb.d/init.sh',
                                    sub_path='init.sh'
                                )
                            ],
                            # Resource limits for homelab environment
                            resources=k8s.core.v1.ResourceRequirementsArgs(
                                requests={
                                    'memory': '512Mi',
                                    'cpu': '250m'
                                },
                                limits={
                                    'memory': '2Gi',
                                    'cpu': '1000m'
                                }
                            ),
                            # Health checks
                            liveness_probe=k8s.core.v1.ProbeArgs(
                                exec=k8s.core.v1.ExecActionArgs(
                                    command=['pg_isready', '-U', 'postgres']
                                ),
                                initial_delay_seconds=30,
                                period_seconds=10,
                                timeout_seconds=5,
                                failure_threshold=3
                            ),
                            readiness_probe=k8s.core.v1.ProbeArgs(
                                exec=k8s.core.v1.ExecActionArgs(
                                    command=['pg_isready', '-U', 'postgres']
                                ),
                                initial_delay_seconds=5,
                                period_seconds=5,
                                timeout_seconds=3,
                                failure_threshold=3
                            )
                        )
                    ],
                    # Security context
                    security_context=k8s.core.v1.PodSecurityContextArgs(
                        fs_group=999,  # postgres group
                        run_as_user=999,  # postgres user
                        run_as_non_root=True
                    ),
                    volumes=[
                        k8s.core.v1.VolumeArgs(
                            name='postgres-config',
                            config_map=k8s.core.v1.ConfigMapVolumeSourceArgs(
                                name='postgres-config'
                            )
                        ),
                        k8s.core.v1.VolumeArgs(
                            name='postgres-init',
                            config_map=k8s.core.v1.ConfigMapVolumeSourceArgs(
                                name='postgres-init',
                                default_mode=0o755
                            )
                        )
                    ]
                )
            ),
            volume_claim_templates=[k8s.core.v1.PersistentVolumeClaimArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name='postgres-storage'
                ),
                spec=k8s.core.v1.PersistentVolumeClaimSpecArgs(
                    access_modes=['ReadWriteOnce'],
                    storage_class_name=storage_class,
                    resources=k8s.core.v1.VolumeResourceRequirementsArgs(
                        requests={'storage': storage_size}
                    )
                )
            )]
        ),
        opts=p.ResourceOptions(
            provider=k8s_provider,
            depends_on=[credentials_secret, postgres_config, init_script]
        ),
    )

    # Create service for PostgreSQL
    service = k8s.core.v1.Service(
        'postgres-service',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres',
            namespace=namespace_name,
            labels={'app': 'postgres'}
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            selector={'app': 'postgres'},
            ports=[k8s.core.v1.ServicePortArgs(
                name='postgres',
                port=5432,
                target_port='postgres'
            )],
            type='ClusterIP'
        ),
        opts=k8s_opts,
    )

    # Optional: Create service for metrics (if using postgres_exporter)
    metrics_service = k8s.core.v1.Service(
        'postgres-metrics',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres-metrics',
            namespace=namespace_name,
            labels={
                'app': 'postgres',
                'component': 'metrics'
            }
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            selector={'app': 'postgres'},
            ports=[k8s.core.v1.ServicePortArgs(
                name='metrics',
                port=9187,
                target_port=9187
            )],
            type='ClusterIP'
        ),
        opts=k8s_opts,
    )

    postgres_service = service.metadata.name

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


def create_postgres_exporter_sidecar():
    """
    Configuration for postgres_exporter as a sidecar container.
    This would be added to the StatefulSet containers list for metrics collection.
    """
    return k8s.core.v1.ContainerArgs(
        name='postgres-exporter',
        image='prometheuscommunity/postgres-exporter:v0.15.0',
        env=[
            k8s.core.v1.EnvVarArgs(
                name='DATA_SOURCE_NAME',
                value='postgresql://paperless:$(POSTGRES_PASSWORD)@localhost:5432/paperless?sslmode=disable'
            ),
            k8s.core.v1.EnvVarArgs(
                name='POSTGRES_PASSWORD',
                value_from=k8s.core.v1.EnvVarSourceArgs(
                    secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                        name='postgres-credentials',
                        key='paperless-password'
                    )
                )
            ),
        ],
        ports=[k8s.core.v1.ContainerPortArgs(
            name='metrics',
            container_port=9187
        )],
        resources=k8s.core.v1.ResourceRequirementsArgs(
            requests={
                'memory': '64Mi',
                'cpu': '50m'
            },
            limits={
                'memory': '128Mi',
                'cpu': '100m'
            }
        )
    )