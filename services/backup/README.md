# Backup Service

This service provides automated backups of NFS volumes to IDrive E2 S3 storage using restic.

## Configuration

The service is configured via `Pulumi.prod.yaml` with the following key settings:

- **Schedule**: Daily at 1 AM (`0 1 * * *`)
- **Compression**: Maximum (`max`) - optimized for 40 Mbit upload bandwidth
- **Retention**: 14 daily, 8 weekly, 12 monthly, 5 yearly snapshots
- **Storage**: IDrive E2 S3 buckets (separate bucket per volume)

## Volumes

Currently configured volumes:
- `joplin` → `restic-joplin` bucket

## Local Restic Operations

Use the helper script to check and restore backups locally:

### Setup

1. **Automatic (Recommended)**: The script automatically loads credentials from 1Password using the same references as the Pulumi configuration. Just make sure you're signed in:
   ```bash
   op account list
   op signin  # if needed
   ```

2. **Manual**: Alternatively, set environment variables or use a `.env` file:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

3. Install required tools:
   ```bash
   # Install restic
   # macOS: brew install restic
   # Ubuntu/Debian: sudo apt install restic
   # Or download from: https://restic.readthedocs.io/en/latest/020_installation.html

   # Install 1Password CLI (for automatic credential loading)
   # macOS: brew install --cask 1password-cli
   # Ubuntu/Debian: See https://developer.1password.com/docs/cli/get-started/
   ```

### Usage

```bash
# List available snapshots
./scripts/restic-helper.sh joplin snapshots

# Check repository integrity
./scripts/restic-helper.sh joplin check

# Show repository statistics
./scripts/restic-helper.sh joplin stats

# List files in latest snapshot
./scripts/restic-helper.sh joplin ls latest

# Search for specific files
./scripts/restic-helper.sh joplin find --iname "*.txt"

# Restore latest snapshot
./scripts/restic-helper.sh joplin restore latest --target ./restored-joplin

# Restore specific snapshot
./scripts/restic-helper.sh joplin restore abc123def --target ./restored-joplin

# Mount repository as filesystem (read-only)
mkdir /tmp/restic-mount
./scripts/restic-helper.sh joplin mount /tmp/restic-mount
# Browse files, then unmount with: fusermount -u /tmp/restic-mount
```

### Examples

```bash
# Quick health check
./scripts/restic-helper.sh joplin check --read-data-subset=5%

# List snapshots with size info
./scripts/restic-helper.sh joplin snapshots --compact

# Restore a single file
./scripts/restic-helper.sh joplin restore latest --target . --include "path/to/important-file.txt"

# Show differences between snapshots
./scripts/restic-helper.sh joplin diff abc123def def456ghi
```

## Monitoring

The CronJob creates Kubernetes events and logs that can be monitored via:
- `kubectl logs -n backup cronjob/backup-cronjob`
- Prometheus metrics (if monitoring is configured)
- CronJob status: `kubectl get cronjobs -n backup`

## Troubleshooting

### Backup Job Failures
```bash
# Check CronJob status
kubectl get cronjobs -n backup

# View recent job logs
kubectl logs -n backup job/backup-cronjob-<timestamp>

# Check NFS mount issues
kubectl describe pod -n backup <backup-pod-name>
```

### Repository Issues
```bash
# Check repository integrity
./scripts/restic-helper.sh joplin check

# Repair repository if needed
./scripts/restic-helper.sh joplin check --read-data
./scripts/restic-helper.sh joplin rebuild-index
```

## Adding New Volumes

To backup additional volumes:

1. Add the volume configuration to `Pulumi.prod.yaml`:
   ```yaml
   volumes:
     - name: "new-volume"
       nfs-server: "synology.tobiash.net"
       nfs-path: "/volume2/new-data"
       bucket: "restic-new-volume"
   ```

2. Update the helper script's volume mapping in `scripts/restic-helper.sh`

3. Deploy the updated configuration:
   ```bash
   (cd services/backup && pulumi up --stack prod)
   ```
