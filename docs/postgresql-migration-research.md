# PostgreSQL Migration Research: Moving Away from Bitnami Charts

## Executive Summary

Due to Bitnami's announced changes to their container images and charts (see [issue #35164](https://github.com/bitnami/charts/issues/35164)), we need to migrate away from using the Bitnami PostgreSQL Helm chart. This document provides comprehensive research on alternatives and migration strategies.

## Current State Analysis

### Current Setup
- **Chart**: `oci://registry-1.docker.io/bitnamicharts/postgresql`
- **Version**: 16.7.21
- **Services Using PostgreSQL**: Only `paperless` service
- **Database**: Single PostgreSQL instance for Paperless-ngx document management
- **Features Used**:
  - Basic PostgreSQL deployment
  - Metrics enabled
  - Port forwarding for management
  - Random password generation
  - Database and user creation via Pulumi PostgreSQL provider

### Code Impact
- Central deployment in `utils/src/utils/postgres.py`
- Configuration in `services/paperless/Pulumi.prod.yaml`
- Database management in `services/paperless/paperless/paperless.py`

## Alternative Solutions Research

### 1. CloudNativePG (Recommended)

**Overview**: CloudNativePG is a modern Kubernetes operator for PostgreSQL, designed for cloud-native environments.

**Pros**:
- ✅ Cloud Native Computing Foundation (CNCF) project
- ✅ Built specifically for Kubernetes
- ✅ Advanced features: automated failover, backup/restore, monitoring
- ✅ Support for PostgreSQL streaming replication
- ✅ Prometheus metrics out of the box
- ✅ Active development and strong community
- ✅ Supports PostgreSQL 12-16
- ✅ Built-in backup to S3/MinIO
- ✅ Rolling updates and self-healing

**Cons**:
- ❌ More complex initial setup compared to simple Helm chart
- ❌ Requires learning operator concepts
- ❌ Additional CRDs in cluster

**Migration Complexity**: Medium
- Requires operator installation
- Database migration via backup/restore
- Configuration changes to use operator CRDs

**Best For**: Production workloads requiring high availability and advanced PostgreSQL features

### 2. Zalando PostgreSQL Operator

**Overview**: Battle-tested PostgreSQL operator from Zalando, used in production for years.

**Pros**:
- ✅ Proven in large-scale production environments
- ✅ Mature and stable (5+ years in development)
- ✅ Advanced HA features (Patroni-based)
- ✅ Built-in connection pooling (PgBouncer)
- ✅ Automated backup and restore
- ✅ Supports major PostgreSQL versions
- ✅ Good documentation and community

**Cons**:
- ❌ More opinionated setup
- ❌ Complex for simple use cases
- ❌ Heavier resource requirements
- ❌ Some features may be overkill for single-service setup

**Migration Complexity**: High
- Requires operator and extensive configuration
- More moving parts to manage

**Best For**: Multi-tenant environments or applications requiring enterprise-grade PostgreSQL

### 3. Official PostgreSQL Helm Charts

**Overview**: Community-maintained Helm charts for PostgreSQL.

**Options**:
- **postgresql** by Bitnami (affected by the same issue)
- **postgresql** by charts.bitnami.com (same issue)
- **postgresql-ha** for high availability setups

**Pros**:
- ✅ Direct replacement for current setup
- ✅ Minimal migration effort
- ✅ Well-documented and maintained
- ✅ Flexible configuration options

**Cons**:
- ❌ Most are still Bitnami-based (same issue)
- ❌ Limited official alternatives
- ❌ Less advanced features compared to operators

**Migration Complexity**: Low to Medium
- Direct chart replacement possible
- May still face same Bitnami issues

**Best For**: Simple, single-instance PostgreSQL needs

### 4. CrunchyData PostgreSQL Operator

**Overview**: Enterprise-grade PostgreSQL operator with comprehensive features.

**Pros**:
- ✅ Enterprise-focused with extensive features
- ✅ Excellent security features
- ✅ Comprehensive backup and disaster recovery
- ✅ Built-in monitoring and alerting
- ✅ Support for PostgreSQL extensions
- ✅ Good documentation

**Cons**:
- ❌ Complex setup and configuration
- ❌ Resource-intensive
- ❌ May be overkill for homelab use
- ❌ Enterprise focus may not align with homelab needs

**Migration Complexity**: High
- Extensive configuration required
- Learning curve for enterprise features

**Best For**: Enterprise environments requiring comprehensive PostgreSQL management

### 5. Custom Kubernetes StatefulSet

**Overview**: Manual deployment using Kubernetes StatefulSet with official PostgreSQL images.

**Pros**:
- ✅ Full control over configuration
- ✅ No dependency on third-party charts
- ✅ Uses official PostgreSQL images
- ✅ Simple and transparent
- ✅ Easy to customize

**Cons**:
- ❌ Manual management of all PostgreSQL aspects
- ❌ No built-in backup/restore automation
- ❌ No advanced HA features
- ❌ More maintenance overhead
- ❌ Requires PostgreSQL expertise

**Migration Complexity**: Medium
- Custom YAML deployment required
- Manual backup/restore implementation

**Best For**: Simple setups where full control is preferred over convenience

## Comparison Matrix

| Feature | CloudNativePG | Zalando | Official Charts | CrunchyData | Custom StatefulSet |
|---------|---------------|---------|----------------|-------------|-------------------|
| Setup Complexity | Medium | High | Low | High | Medium |
| HA Support | ✅ | ✅ | ❌ | ✅ | ❌ |
| Automated Backup | ✅ | ✅ | ❌ | ✅ | ❌ |
| Monitoring | ✅ | ✅ | ✅ | ✅ | Manual |
| Resource Usage | Medium | High | Low | High | Low |
| Community Support | Good | Good | Limited | Good | N/A |
| Homelab Fit | ✅ | ❌ | ✅ | ❌ | ✅ |

## Recommendation

**Primary Recommendation: CloudNativePG**

For the homelab environment, CloudNativePG offers the best balance of:
- Modern cloud-native design
- Reasonable complexity for the benefits provided
- Built-in backup and monitoring capabilities
- Future-proof architecture
- Active development and CNCF backing

**Fallback Option: Custom StatefulSet**

If CloudNativePG proves too complex, a custom StatefulSet deployment provides:
- Simple, transparent setup
- Full control over configuration
- No external dependencies
- Easy to understand and maintain

## Migration Strategy

### Phase 1: Preparation
1. **Backup Current Database**
   - Create full backup of existing paperless database
   - Test backup restoration procedures
   - Document current database schema and data

2. **Setup New PostgreSQL**
   - Deploy CloudNativePG operator
   - Create new PostgreSQL cluster
   - Verify connectivity and basic operations

### Phase 2: Migration
1. **Data Migration**
   - Stop paperless application
   - Perform final backup of existing database
   - Restore data to new PostgreSQL instance
   - Update connection configuration

2. **Configuration Updates**
   - Modify `utils/postgres.py` to use new deployment method
   - Update Pulumi configuration files
   - Test application connectivity

### Phase 3: Validation and Cleanup
1. **Testing**
   - Verify paperless functionality
   - Test backup and restore procedures
   - Monitor system performance

2. **Cleanup**
   - Remove old Bitnami deployment
   - Update documentation
   - Plan ongoing maintenance procedures

## Implementation Timeline

- **Week 1**: Research completion and decision finalization
- **Week 2**: CloudNativePG operator setup and testing
- **Week 3**: Migration implementation and testing
- **Week 4**: Validation, cleanup, and documentation

## Risk Assessment

### High Risk
- Data loss during migration
- Extended downtime
- Configuration incompatibilities

### Mitigation Strategies
- Comprehensive backup strategy
- Staged migration with rollback plan
- Thorough testing in development environment
- Documented rollback procedures

## Next Steps

1. ✅ Complete research and alternatives assessment
2. ⏳ Set up test environment for CloudNativePG
3. ⏳ Develop migration scripts and procedures
4. ⏳ Create backup and rollback plans
5. ⏳ Execute migration in production

## References

- [CloudNativePG Documentation](https://cloudnative-pg.io/)
- [Zalando PostgreSQL Operator](https://github.com/zalando/postgres-operator)
- [CrunchyData PGO](https://github.com/CrunchyData/postgres-operator)
- [Bitnami Charts Issue #35164](https://github.com/bitnami/charts/issues/35164)
- [Kubernetes StatefulSet Documentation](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
