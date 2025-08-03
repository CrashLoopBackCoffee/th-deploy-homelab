"""Paperless restore orchestration using Job."""

import textwrap
import time

from typing import Optional

import pulumi as p
import pulumi_kubernetes as k8s

from .config import ComponentConfig

RESTORE_SCRIPT = textwrap.dedent(
    """\
    #!/bin/sh
    set -eu

    # Log with timestamp
    log() {{
        echo "$(date '+%Y-%m-%d %H:%M:%S') $1"
    }}

    log "Starting Paperless restore process..."

    # kubectl is already available in this image at /usr/local/bin/kubectl
    KUBECTL="/usr/local/bin/kubectl"

    # Parse arguments
    SNAPSHOT_ID="${{1:-latest}}"
    RESTORE_PATH="${{2:-/tmp/paperless-restore}}"

    log "Using kubectl version: $($KUBECTL version --client --short 2>/dev/null || $KUBECTL version --client)"
    log "Restoring snapshot: $SNAPSHOT_ID"
    log "Restore path: $RESTORE_PATH"

    # Step 1: Restore data from restic repository
    log "Step 1: Restoring data from restic repository..."
    $KUBECTL exec paperless-0 -c restic -- restic restore "$SNAPSHOT_ID" --target "$RESTORE_PATH"

    log "Data restored to $RESTORE_PATH"

    # Step 2: Import the restored documents
    log "Step 2: Importing restored documents..."
    $KUBECTL exec paperless-0 -c paperless -- document_importer \\
        "$RESTORE_PATH" \\
        --no-progress-bar

    log "Step 3: Cleaning up temporary restore data..."
    $KUBECTL exec paperless-0 -c paperless -- rm -rf "$RESTORE_PATH"

    log "Paperless restore completed successfully!"
    log ""
    log "IMPORTANT: Since archives and thumbnails were not backed up, you should regenerate them:"
    log "  1. Regenerate thumbnails: kubectl exec paperless-0 -c paperless -- python manage.py document_thumbnails"
    log "  2. Regenerate archives: kubectl exec paperless-0 -c paperless -- python manage.py document_archiver"
    log "  3. Update search index: kubectl exec paperless-0 -c paperless -- python manage.py document_index reindex"
    log ""
    log "Optional post-processing commands:"
    log "  - Detect duplicates: kubectl exec paperless-0 -c paperless -- python manage.py document_retagger"
    log "  - Update classification: kubectl exec paperless-0 -c paperless -- python manage.py document_create_classifier"
    log ""
    log "These commands may take some time depending on the number of documents."
    log "Please verify that all documents were imported correctly before proceeding."
    """
)


def create_restore_job(
    component_config: ComponentConfig,
    k8s_opts: p.ResourceOptions,
    backup_secret: k8s.core.v1.Secret,
    snapshot_id: str = 'latest',
    job_name: Optional[str] = None,
) -> k8s.batch.v1.Job:
    """Create a one-time Job to restore Paperless data from backup.

    Args:
        component_config: The component configuration
        k8s_opts: Kubernetes resource options
        backup_secret: The backup secret containing restic password and rclone config
        snapshot_id: The restic snapshot ID to restore (default: "latest")
        job_name: Custom job name (default: auto-generated with timestamp)
    """

    timestamp = str(int(time.time()))
    if job_name is None:
        job_name = f'paperless-restore-{timestamp}'

    # ConfigMap with restore script
    restore_script = k8s.core.v1.ConfigMap(
        'paperless-restore-script',
        metadata={'name': f'paperless-restore-script-{timestamp}'},
        data={
            'restore.sh': RESTORE_SCRIPT
        },
        opts=k8s_opts,
    )

    # Job for restore orchestration
    return k8s.batch.v1.Job(
        'paperless-restore',
        metadata={'name': job_name},
        spec={
            'template': {
                'spec': {
                    'service_account_name': 'paperless-backup',  # Reuse backup service account
                    'restart_policy': 'Never',
                    'containers': [
                        {
                            'name': 'restore-orchestrator',
                            'image': f'registry.k8s.io/conformance:v{component_config.backup.kubectl_version}',
                            'command': ['/bin/sh'],
                            'args': ['/scripts/restore.sh', snapshot_id],
                            'env': [
                                {
                                    'name': 'RESTIC_PASSWORD',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': backup_secret.metadata.name,
                                            'key': 'restic-password',
                                        }
                                    },
                                }
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'restore-script',
                                    'mount_path': '/scripts',
                                    'read_only': True,
                                },
                            ],
                        }
                    ],
                    'volumes': [
                        {
                            'name': 'restore-script',
                            'config_map': {
                                'name': restore_script.metadata['name'],
                                'default_mode': 0o755,
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )
