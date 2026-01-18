# Ingress Service

This service manages ingress and certificate deployment for the homelab infrastructure.

## Components

### 1. Cloudflared Tunnels

Manages Cloudflare tunnels for secure ingress to internal services without exposing ports.

### 2. Synology Certificate Deployment

Automatically deploys TLS certificates from cert-manager to Synology DSM.

## Configuration

### Synology Certificate Deployment

To enable automatic certificate deployment to Synology NAS:

```yaml
config:
  ingress:config:
    # ... existing cloudflare/cloudflared config ...

    synology:
      host: nas.example.com
      port: 5001  # Optional, defaults to 5000
      scheme: https  # Optional, defaults to http
      username:
        ref: op://Homelab/Synology Cert Updater/username
      password:
        ref: op://Homelab/Synology Cert Updater/password
      certs:
        - hostname: nas.example.com
        - hostname: "*.example.com"
```

### Configuration Fields

#### `synology` (optional)

Main configuration for Synology certificate deployment.

- **`host`** (required): Synology DSM hostname or IP address
- **`port`** (optional, default: 5000): DSM API port
- **`scheme`** (optional, default: http): API scheme (`http` or `https`)
- **`username`** (required): Admin username for DSM (2FA must be disabled for this user) - 1Password reference
- **`password`** (required): Admin password - 1Password reference
- **`certs`** (required): List of certificates to deploy

#### `certs[]`

Each certificate entry requires:

- **`hostname`**: The hostname (used as certificate description in DSM)

The Kubernetes secret name is automatically derived from the hostname:
- `nas.example.com` → secret name: `nas-example-com-tls`
- `*.example.com` → secret name: `wildcard-example-com-tls`

### Prerequisites

1. **Synology User Account**: Create a dedicated user without 2FA enabled
2. **Admin Permissions**: User must be in the `administrators` group
3. **Cert-Manager Secrets**: Each secret must contain `tls.crt` (full chain) and `tls.key`

### How It Works

For each certificate in the configuration:

1. A CronJob is created in the `synology-certs` namespace
2. The job runs daily at 3 AM
3. The deployment script:
   - Authenticates to Synology DSM API
   - Splits the certificate chain into server cert and intermediates
   - Uploads/updates the certificate with the hostname as description
   - Logs out

### Example with Cert-Manager

```yaml
# cert-manager Certificate resource
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: nas-cert
  namespace: cert-manager  # Or your cert namespace
spec:
  secretName: nas-example-com-tls  # Must match derived name
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - nas.example.com
```

Then reference the hostname in your Pulumi configuration:

```yaml
synology:
  certs:
    - hostname: nas.example.com  # Secret name will be: nas-example-com-tls
```

### Security Considerations

- Store Synology credentials using 1Password references
- Create a dedicated service account for certificate updates
- Disable 2FA for the service account (required for API authentication)
- Use HTTPS (`scheme: https`) when possible
- Limit network access to DSM API

### Troubleshooting

#### Check CronJob logs:

```bash
kubectl get cronjobs -n synology-certs
kubectl get jobs -n synology-certs
kubectl logs -n synology-certs job/<job-name>
```

#### Test manually:

```bash
kubectl create job -n synology-certs test-run --from=cronjob/synology-cert-<hostname>
kubectl logs -n synology-certs job/test-run -f
```

#### Enable debug logging:

Edit the CronJob to add:

```yaml
env:
  - name: DEBUG
    value: "1"
```
