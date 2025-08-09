# th-deploy-homelab

## Google Drive Backups with rclone

To configure rclone for use with Google Drive (required for Paperless backups), follow this guide:

- [Setting up rclone with Google Drive (tcude.net)](https://tcude.net/setting-up-rclone-with-google-drive/)

This guide covers:
- Creating Google API credentials
- Authorizing rclone
- Setting up your `rclone.conf` file

After configuration, copy your `rclone.conf` to a secure location and reference it in your backup scripts.

## Paperless Dual Backups (Google Drive + IDrive E2)

Paperless now supports an optional secondary restic repository on IDrive E2 (S3-compatible) for redundancy.

Configuration (in `services/paperless/Pulumi.prod.yaml` under `backup:`):

```
idrive-enabled: true                # set to true to enable sidecar + secondary backup
idrive-endpoint: https://<endpoint> # e.g. https://xxxx.idrivee2-XX.com
idrive-bucket: restic-paperless     # bucket name (must exist in IDrive E2)
idrive-access-key-id: op://...      # 1Password ref (Access Key ID)
idrive-secret-access-key: op://...  # 1Password ref (Secret Access Key)
```

Implementation details:
- Adds a `restic-idrive` sidecar container to the Paperless StatefulSet when `idrive-enabled` is true.
- Primary repository uses rclone to Google Drive (`rclone:gdrive:<repository-path>`).
- Secondary repository uses native restic S3 backend (`s3:<endpoint>/<bucket>/<repository-path>`).
- Existing CronJob detects sidecar and runs backup + forget/prune against both repositories.

Operational notes:
- Ensure bucket exists and credentials have read/write (s3:List*, s3:Get*, s3:Put*, s3:DeleteObject).
- Automatic repository initialization: the backup CronJob now proactively checks both primary and secondary repositories and runs `restic init` on any that are missing before the first backup. No manual init step is required.
- To disable secondary backup set `idrive-enabled: false` (sidecar removed; CronJob skips secondary steps).
- Monitor backup logs in CronJob pods (`kubectl logs -l job-name=<job>`); look for lines containing `Secondary restic backup`.

Restore procedure for IDrive repository (example):
```
export RESTIC_REPOSITORY=s3:https://<endpoint>/<bucket>/<repository-path>
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export RESTIC_PASSWORD=...
restic snapshots
restic restore <snapshot-id> --target ./restore
```

Test restores regularly to validate redundancy.
