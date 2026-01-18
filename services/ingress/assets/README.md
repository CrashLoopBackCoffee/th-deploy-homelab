# Synology DSM Certificate Deployment Script

## Overview

`synology-cert-deploy.sh` is a standalone bash script for deploying TLS certificates to Synology DSM without requiring acme.sh. It's designed to run in Kubernetes cronjobs with certificates mounted as secrets.

## Features

- ✅ Pure bash/curl implementation (no acme.sh dependency)
- ✅ Simple authentication (no 2FA complexity)
- ✅ Automatically creates certificate if it doesn't exist
- ✅ Automatically detects and preserves default certificate status
- ✅ Comprehensive error handling and logging
- ✅ Designed for non-interactive Kubernetes cronjob execution

## Prerequisites

- Synology DSM with admin access (2FA must be disabled for the service account)
- `curl` available in the container
- TLS certificate files (key, cert, CA chain)

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SYNO_HOSTNAME` | Synology hostname or IP address | `nas.example.com` or `192.168.1.100` |
| `SYNO_USERNAME` | Admin username | `cert-updater` |
| `SYNO_PASSWORD` | Admin password | `SecurePassword123` |
| `CERT_KEY_FILE` | Path to certificate private key | `/certs/tls.key` |
| `CERT_CERT_FILE` | Path to certificate file (full chain) | `/certs/tls.crt` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SYNO_PORT` | DSM API port | `5000` |
| `SYNO_SCHEME` | API scheme (http/https) | `http` |
| `SYNO_CERTIFICATE` | Certificate description to update | (empty - updates default) |
| `CERT_CA_FILE` | Path to separate CA file (if needed) | Uses `CERT_CERT_FILE` |
| `DEBUG` | Enable verbose logging (`1` to enable) | `0` |

## Kubernetes Usage

### 1. Create Secrets

```yaml
# Certificate secret (from cert-manager or similar)
apiVersion: v1
kind: Secret
metadata:
  name: synology-tls-cert
  namespace: ingress
type: kubernetes.io/tls
data:
  tls.key: <base64-encoded-key>
  tls.crt: <base64-encoded-full-chain>

---
# Synology credentials secret
apiVersion: v1
kind: Secret
metadata:
  name: synology-credentials
  namespace: ingress
type: Opaque
stringData:
  SYNO_HOSTNAME: "nas.example.com"
  SYNO_PORT: "5001"
  SYNO_SCHEME: "https"
  SYNO_USERNAME: "cert-updater"
  SYNO_PASSWORD: "your-secure-password"
  SYNO_CERTIFICATE: "K8s Certificate"
```

### 2. Create ConfigMap with Script

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: synology-cert-deploy-script
  namespace: ingress
data:
  synology-cert-deploy.sh: |
    #!/bin/bash
    # Paste the entire script content here
```

### 3. Create CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: synology-cert-updater
  namespace: ingress
spec:
  # Run daily at 3 AM
  schedule: "0 3 * * *"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: cert-updater
            image: curlimages/curl:latest  # Minimal image with curl
            command:
            - /bin/sh
            - -c
            - |
              # Install bash if not available
              if ! command -v bash >/dev/null 2>&1; then
                apk add --no-cache bash
              fi
              # Run the deployment script
              bash /scripts/synology-cert-deploy.sh
            env:
            # Certificate file paths
            - name: CERT_KEY_FILE
              value: "/certs/tls.key"
            - name: CERT_CERT_FILE
              value: "/certs/tls.crt"
            # Import all Synology configuration from secret
            envFrom:
            - secretRef:
                name: synology-credentials
            volumeMounts:
            - name: certs
              mountPath: /certs
              readOnly: true
            - name: script
              mountPath: /scripts
              readOnly: true
          volumes:
          - name: certs
            secret:
              secretName: synology-tls-cert
          - name: script
            configMap:
              name: synology-cert-deploy-script
              defaultMode: 0755
```

## Manual Testing

Test the script manually before deploying to Kubernetes:

```bash
# Set required environment variables
export SYNO_HOSTNAME="nas.example.com"
export SYNO_USERNAME="admin"
export SYNO_PASSWORD="your-password"
export SYNO_PORT="5001"
export SYNO_SCHEME="https"
export SYNO_CERTIFICATE="Test Certificate"

# Set certificate file paths
export CERT_KEY_FILE="/path/to/tls.key"
export CERT_CERT_FILE="/path/to/tls.crt"

# Optional: Enable debug output
export DEBUG="1"

# Run the script
./synology-cert-deploy.sh
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication failure |
| 2 | Certificate file error |
| 3 | API error |
| 4 | Configuration error |

## Troubleshooting

### Enable Debug Logging
```bash
export DEBUG="1"
```

### Common Issues

1. **"Authentication failed: 2FA is enabled"**
   - Solution: Disable 2FA for the service account or create a dedicated user without 2FA

2. **"Insufficient permissions: User must be administrator"**
   - Solution: Ensure the user is in the administrators group

3. **"Failed to connect to Synology DSM API"**
   - Check network connectivity
   - Verify `SYNO_HOSTNAME` and `SYNO_PORT`
   - Check if firewall allows connections

4. **SSL/TLS errors**
   - The script uses `-k` (insecure) flag for curl to skip certificate verification
   - For production, consider using proper CA certificates

## Security Considerations

- Store credentials in Kubernetes Secrets, never in ConfigMaps or code
- Use RBAC to restrict access to the secrets
- Consider using external secret management (e.g., Sealed Secrets, External Secrets Operator)
- Use HTTPS (`SYNO_SCHEME="https"`) when possible
- Create a dedicated service account without 2FA for certificate updates
- Limit network access to the Synology DSM API

## Integration with Cert-Manager

If using cert-manager, the certificate secret is automatically updated. The cronjob will detect changes and push them to Synology DSM.

Example cert-manager Certificate resource:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: synology-cert
  namespace: ingress
spec:
  secretName: synology-tls-cert
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - nas.example.com
  - "*.example.com"
```

The cronjob will automatically pick up the renewed certificate and deploy it to Synology DSM.
