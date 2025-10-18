# PostgreSQL Deployment Backends

The `utils.postgres.create_postgres` function now supports multiple deployment backends for PostgreSQL in Kubernetes: Bitnami Helm chart and CloudNativePG operator.

## Overview

- **Bitnami (default)**: Simple, single-instance PostgreSQL deployment via Helm
- **CloudNativePG**: Cloud-native PostgreSQL operator with advanced features

## Usage

### Default Bitnami Backend

```python
from utils.postgres import create_postgres

postgres_provider, postgres_service, postgres_port = create_postgres(
    version='15',
    namespace_name=namespace.metadata.name,
    k8s_provider=k8s_provider,
)
```

### CloudNativePG Backend

```python
from utils.postgres import create_postgres, PostgresBackend

postgres_provider, postgres_service, postgres_port = create_postgres(
    version='16',
    namespace_name=namespace.metadata.name,
    k8s_provider=k8s_provider,
    backend=PostgresBackend.CLOUDNATIVE_PG,
    storage_size='100Gi',
    storage_class='local-path',
)
```

## Backend Comparison

### Bitnami Helm Chart
- **Pros**:
  - Simple, straightforward deployment
  - Single-instance setup
  - Minimal configuration needed
  - Familiar Helm-based approach

- **Cons**:
  - Limited HA/DR capabilities
  - No built-in backup management
  - Less cloud-native

### CloudNativePG
- **Pros**:
  - Cloud-native PostgreSQL operator
  - Advanced monitoring support
  - Extensible configuration
  - PodMonitor integration for Prometheus
  - Better resource utilization
  - Performance tuned for homelab

- **Cons**:
  - Requires CloudNativePG operator to be installed
  - More complex deployment model
  - Additional CRDs in cluster

## CloudNativePG Prerequisites

Before using the CloudNativePG backend, ensure the CloudNativePG operator is deployed:

```python
from kubernetes.cloudnativepg import create_cloudnative_pg
from kubernetes.config import ComponentConfig

# In your kubernetes service __main__.py
cloudnative_pg = create_cloudnative_pg(component_config, k8s_provider)
```

## Configuration Options

### CloudNativePG Backend Parameters

- `postgres_version`: PostgreSQL version (e.g., "16")
- `storage_size`: PVC size for PostgreSQL data (default: "20Gi")
- `storage_class`: Storage class name (default: "local-path")
- `local_port`: Local port for port-forwarding (default: 15432)

### Default CloudNativePG Settings

The CloudNativePG backend includes optimized PostgreSQL parameters for homelab environments:

- `max_connections`: 100
- `shared_buffers`: 256MB
- `effective_cache_size`: 1GB
- `wal_buffers`: 16MB
- Logging enabled for connections, disconnections, and lock waits

## Connection Details

Both backends return the same interface:

```python
postgres_provider: postgresql.Provider
postgres_service: p.Output[str]
postgres_port: int  # Local forwarded port
```

### Usage Examples

```python
# Create a database
database = postgresql.Database(
    'my-db',
    name='my_database',
    owner='postgres',
    opts=p.ResourceOptions(provider=postgres_provider),
)

# Create a user with specific password
postgres_user = postgresql.Role(
    'app-user',
    login=True,
    password=root_password.result,
    opts=p.ResourceOptions(provider=postgres_provider),
)
```

## Migration Path

Existing services using the Bitnami backend (default) can migrate to CloudNativePG by:

1. Ensuring CloudNativePG operator is deployed
2. Updating the service configuration to pass `backend=PostgresBackend.CLOUDNATIVE_PG`
3. Adjusting storage settings as needed
4. Running `pulumi preview` and `pulumi up`

## Troubleshooting

### CloudNativePG Cluster Not Starting

1. Verify the operator is running: `kubectl get pods -n cnpg-system`
2. Check cluster status: `kubectl describe cluster postgres -n <namespace>`
3. View cluster logs: `kubectl logs -n <namespace> postgres-1`

### Connection Issues

1. Verify port-forward is active: `lsof -i :15432`
2. Check service exists: `kubectl get svc -n <namespace>`
3. View port-forward logs in Pulumi output
