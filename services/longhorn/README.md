# Longhorn Distributed Block Storage

This service deploys [Longhorn](https://longhorn.io/) as a distributed block storage system for the Kubernetes cluster.

## Features

- **Single-node configuration** with 1 replica (configurable for multi-node in the future)
- **Dedicated 200GB disk** mounted at `/var/lib/longhorn` on the k8s node
- **S3 backup integration** to iDrive E2 for automatic backups
- **TLS-secured UI** accessible via LoadBalancer with Let's Encrypt certificate
- **Local DNS record** created via OPNsense Unbound for easy access
- **Non-default StorageClass** (`longhorn`) alongside existing `microk8s-hostpath`

## Configuration

The service is configured via `Pulumi.prod.yaml`:

- **Chart version**: Managed by Renovate for automatic updates
- **Hostname**: `longhorn.tobiash.net` for UI access
- **S3 credentials**: Stored in 1Password (`IDrive e2 Longhorn`)

## Deployment

The deployment includes:

1. **Helm Release** using `k8s.helm.v3.Release` (required due to post-upgrade/pre-delete hooks)
2. **S3 Backup Secret** with AWS-compatible credentials for iDrive E2
3. **StorageClass** for Longhorn volumes with volume expansion enabled
4. **TLS Certificate** via cert-manager for UI access
5. **NGINX Proxy** for TLS termination before forwarding to Longhorn UI
6. **LoadBalancer Service** for external UI access
7. **DNS Record** automatically created in OPNsense for hostname resolution

## Storage Architecture

- **Primary Storage**: `microk8s-hostpath` (default) - Local hostpath storage
- **Distributed Storage**: `longhorn` (non-default) - Distributed block storage with backup

Services can choose their storage class via PVC configuration.

## Access

Once deployed, the Longhorn UI is accessible at:
- **URL**: https://longhorn.tobiash.net
- **Authentication**: Managed by Longhorn (default: no authentication)

## Future Enhancements

When adding more nodes to the cluster:
1. Update replica count in Helm values (`defaultSettings.defaultReplicaCount`)
2. Add additional disks to new nodes
3. Longhorn will automatically balance replicas across nodes

## Dependencies

- Kubernetes cluster with MicroK8s
- cert-manager for TLS certificates
- MetalLB for LoadBalancer services
- OPNsense with Unbound for DNS
- iDrive E2 S3 bucket for backups
