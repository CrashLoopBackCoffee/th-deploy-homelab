# PostgreSQL Migration Plan: CloudNativePG Implementation

## Overview

This document outlines the detailed migration plan from Bitnami PostgreSQL Helm chart to CloudNativePG operator for the Paperless service in the homelab.

## Migration Scenarios

### Scenario 1: CloudNativePG Migration (Recommended)

**Timeline**: 2-3 weeks
**Downtime**: ~2-4 hours
**Complexity**: Medium

#### Prerequisites
- Kubernetes cluster with sufficient resources
- Backup storage (S3/MinIO) configured
- Network policies allowing PostgreSQL traffic

#### Migration Steps

##### Phase 1: Operator Setup (Week 1)
1. **Install CloudNativePG Operator**
   ```yaml
   # Add to kubernetes service or create separate operator deployment
   apiVersion: v1
   kind: Namespace
   metadata:
     name: cnpg-system
   ---
   # CloudNativePG operator deployment
   ```

2. **Create New PostgreSQL Cluster**
   ```yaml
   apiVersion: postgresql.cnpg.io/v1
   kind: Cluster
   metadata:
     name: paperless-postgres
     namespace: paperless
   spec:
     instances: 1
     postgresql:
       parameters:
         max_connections: "100"
         shared_buffers: "256MB"
         effective_cache_size: "1GB"
     bootstrap:
       initdb:
         database: paperless
         owner: paperless
         secret:
           name: paperless-postgres-credentials
     storage:
       size: 20Gi
       storageClass: local-path
     monitoring:
       enabled: true
   ```

3. **Test New Cluster**
   - Verify cluster creation
   - Test connectivity
   - Validate metrics collection

##### Phase 2: Data Migration (Week 2)
1. **Backup Current Database**
   ```bash
   # Create backup from current Bitnami deployment
   kubectl exec -n paperless postgres-0 -- pg_dumpall -U postgres > paperless_backup.sql
   ```

2. **Prepare Migration Scripts**
   - Create database restoration script
   - Prepare configuration updates
   - Test migration process in staging

3. **Execute Migration**
   - Stop Paperless application
   - Perform final backup
   - Restore to new PostgreSQL cluster
   - Update application configuration

##### Phase 3: Configuration Update (Week 2-3)
1. **Update Pulumi Code**
   - Modify `utils/postgres.py` to use CloudNativePG
   - Update configuration models
   - Test deployment

2. **Application Configuration**
   - Update database connection strings
   - Verify application functionality
   - Monitor performance

#### Code Changes Required

##### New `utils/postgres_cnpg.py`
```python
import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

def create_cnpg_postgres(
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    storage_size: str = "20Gi",
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL using CloudNativePG operator"""

    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    # Create credentials secret
    root_password = pulumi_random.RandomPassword(
        'postgres-password',
        length=24,
    )

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

    # Create PostgreSQL cluster
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
            'postgresql': {
                'parameters': {
                    'max_connections': '100',
                    'shared_buffers': '256MB',
                    'effective_cache_size': '1GB',
                }
            },
            'bootstrap': {
                'initdb': {
                    'database': 'paperless',
                    'owner': 'paperless',
                    'secret': {
                        'name': 'paperless-postgres-credentials'
                    }
                }
            },
            'storage': {
                'size': storage_size,
                'storageClass': 'local-path'
            },
            'monitoring': {
                'enabled': True
            }
        },
        opts=p.ResourceOptions(
            provider=k8s_provider,
            depends_on=[credentials_secret]
        ),
    )

    # Service name for CloudNativePG
    postgres_service = p.Output.concat(cluster.metadata.name, '-rw')

    # Port forwarding setup
    postgres_port = utils.port_forward.ensure_port_forward(
        local_port=local_port,
        namespace=namespace_name,
        resource_type=utils.port_forward.ResourceType.SERVICE,
        resource_name=postgres_service,
        target_port='5432',
        k8s_provider=k8s_provider,
    )

    return (
        postgresql.Provider(
            'postgres',
            host='localhost',
            port=postgres_port,
            sslmode='disable',
            username='paperless',
            password=root_password.result,
        ),
        postgres_service,
        5432,
    )
```

##### Updated Configuration Models
```python
# In paperless/config.py
class PostgresConfig(pydantic.BaseModel):
    # Remove version field as CloudNativePG manages versions
    storage_size: str = "20Gi"
    instance_count: int = 1
```

### Scenario 2: Custom StatefulSet Migration (Fallback)

**Timeline**: 1-2 weeks
**Downtime**: ~1-2 hours
**Complexity**: Low-Medium

#### Migration Steps

##### Phase 1: StatefulSet Creation
1. **Create PostgreSQL StatefulSet**
   ```yaml
   apiVersion: apps/v1
   kind: StatefulSet
   metadata:
     name: postgres
     namespace: paperless
   spec:
     serviceName: postgres
     replicas: 1
     selector:
       matchLabels:
         app: postgres
     template:
       metadata:
         labels:
           app: postgres
       spec:
         containers:
         - name: postgres
           image: postgres:16
           env:
           - name: POSTGRES_DB
             value: paperless
           - name: POSTGRES_USER
             value: paperless
           - name: POSTGRES_PASSWORD
             valueFrom:
               secretKeyRef:
                 name: postgres-credentials
                 key: password
           ports:
           - containerPort: 5432
           volumeMounts:
           - name: postgres-storage
             mountPath: /var/lib/postgresql/data
     volumeClaimTemplates:
     - metadata:
         name: postgres-storage
       spec:
         accessModes: ["ReadWriteOnce"]
         resources:
           requests:
             storage: 20Gi
   ```

2. **Create Service**
   ```yaml
   apiVersion: v1
   kind: Service
   metadata:
     name: postgres
     namespace: paperless
   spec:
     selector:
       app: postgres
     ports:
     - port: 5432
       targetPort: 5432
   ```

#### Code Changes Required

##### Updated `utils/postgres.py`
```python
def create_postgres_statefulset(
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    postgres_version: str = "16",
    storage_size: str = "20Gi",
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    """Create PostgreSQL using StatefulSet"""

    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    root_password = pulumi_random.RandomPassword(
        'postgres-password',
        length=24,
    )

    # Create credentials secret
    credentials_secret = k8s.core.v1.Secret(
        'postgres-credentials',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres-credentials',
            namespace=namespace_name,
        ),
        string_data={
            'password': root_password.result,
        },
        opts=k8s_opts,
    )

    # Create StatefulSet
    statefulset = k8s.apps.v1.StatefulSet(
        'postgres',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres',
            namespace=namespace_name,
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
                    containers=[k8s.core.v1.ContainerArgs(
                        name='postgres',
                        image=f'postgres:{postgres_version}',
                        env=[
                            k8s.core.v1.EnvVarArgs(
                                name='POSTGRES_DB',
                                value='paperless'
                            ),
                            k8s.core.v1.EnvVarArgs(
                                name='POSTGRES_USER',
                                value='paperless'
                            ),
                            k8s.core.v1.EnvVarArgs(
                                name='POSTGRES_PASSWORD',
                                value_from=k8s.core.v1.EnvVarSourceArgs(
                                    secret_key_ref=k8s.core.v1.SecretKeySelectorArgs(
                                        name='postgres-credentials',
                                        key='password'
                                    )
                                )
                            ),
                        ],
                        ports=[k8s.core.v1.ContainerPortArgs(
                            container_port=5432
                        )],
                        volume_mounts=[k8s.core.v1.VolumeMountArgs(
                            name='postgres-storage',
                            mount_path='/var/lib/postgresql/data'
                        )]
                    )]
                )
            ),
            volume_claim_templates=[k8s.core.v1.PersistentVolumeClaimArgs(
                metadata=k8s.meta.v1.ObjectMetaArgs(
                    name='postgres-storage'
                ),
                spec=k8s.core.v1.PersistentVolumeClaimSpecArgs(
                    access_modes=['ReadWriteOnce'],
                    resources=k8s.core.v1.VolumeResourceRequirementsArgs(
                        requests={'storage': storage_size}
                    )
                )
            )]
        ),
        opts=p.ResourceOptions(
            provider=k8s_provider,
            depends_on=[credentials_secret]
        ),
    )

    # Create service
    service = k8s.core.v1.Service(
        'postgres-service',
        metadata=k8s.meta.v1.ObjectMetaArgs(
            name='postgres',
            namespace=namespace_name,
        ),
        spec=k8s.core.v1.ServiceSpecArgs(
            selector={'app': 'postgres'},
            ports=[k8s.core.v1.ServicePortArgs(
                port=5432,
                target_port=5432
            )]
        ),
        opts=k8s_opts,
    )

    postgres_service = service.metadata.name

    # Port forwarding setup
    postgres_port = utils.port_forward.ensure_port_forward(
        local_port=local_port,
        namespace=namespace_name,
        resource_type=utils.port_forward.ResourceType.SERVICE,
        resource_name=postgres_service,
        target_port=5432,
        k8s_provider=k8s_provider,
    )

    return (
        postgresql.Provider(
            'postgres',
            host='localhost',
            port=postgres_port,
            sslmode='disable',
            username='paperless',
            password=root_password.result,
        ),
        postgres_service,
        5432,
    )
```

## Data Migration Procedures

### Backup Strategy
1. **Pre-migration Backup**
   ```bash
   kubectl exec -n paperless postgres-0 -- pg_dumpall -U postgres > full_backup.sql
   kubectl exec -n paperless postgres-0 -- pg_dump -U postgres paperless > paperless_db_backup.sql
   ```

2. **Verification**
   ```bash
   # Verify backup integrity
   grep -c "COPY" paperless_db_backup.sql
   tail -20 paperless_db_backup.sql  # Should end with success indicators
   ```

### Restoration Process
1. **Prepare New Database**
   ```bash
   # Connect to new PostgreSQL instance
   kubectl exec -n paperless paperless-postgres-1 -- psql -U paperless -d paperless
   ```

2. **Restore Data**
   ```bash
   kubectl exec -i -n paperless paperless-postgres-1 -- psql -U paperless -d paperless < paperless_db_backup.sql
   ```

3. **Verify Migration**
   ```sql
   -- Check table counts
   SELECT schemaname, tablename, n_tup_ins, n_tup_upd, n_tup_del
   FROM pg_stat_user_tables;

   -- Verify specific Paperless tables
   SELECT COUNT(*) FROM documents_document;
   SELECT COUNT(*) FROM documents_tag;
   ```

## Rollback Procedures

### CloudNativePG Rollback
1. **Immediate Rollback**
   - Revert Pulumi configuration
   - Redeploy Bitnami chart
   - Restore from backup

2. **Extended Rollback**
   - Keep new PostgreSQL running
   - Switch application back to old instance
   - Migrate recent data back

### StatefulSet Rollback
1. **Configuration Rollback**
   - Revert `utils/postgres.py` changes
   - Redeploy Bitnami chart
   - Update application configuration

## Testing and Validation

### Pre-Migration Testing
1. **Backup/Restore Testing**
   - Test backup procedures
   - Verify restoration process
   - Validate data integrity

2. **Performance Testing**
   - Benchmark current setup
   - Compare with new deployment
   - Validate response times

### Post-Migration Validation
1. **Functional Testing**
   - Verify Paperless functionality
   - Test document upload/search
   - Validate user authentication

2. **Performance Monitoring**
   - Monitor resource usage
   - Check response times
   - Validate backup operations

## Monitoring and Alerting

### CloudNativePG Monitoring
- Built-in Prometheus metrics
- PostgreSQL performance metrics
- Backup operation status
- Cluster health indicators

### Custom Monitoring
- Database connection health
- Query performance metrics
- Storage usage tracking
- Application-specific metrics

## Conclusion

Both migration scenarios provide viable paths away from Bitnami PostgreSQL:

1. **CloudNativePG** offers advanced features and future-proofing at the cost of increased complexity
2. **Custom StatefulSet** provides simplicity and control with manual management overhead

The recommendation is to proceed with CloudNativePG for its advanced features and industry-standard approach, with the StatefulSet option as a proven fallback strategy.
