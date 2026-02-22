import pathlib

import jinja2
import pulumi as p
import pulumi_kubernetes as k8s

from backup.config import ComponentConfig


def create_backup_cronjob(
    component_config: ComponentConfig, k8s_opts: p.ResourceOptions
) -> k8s.batch.v1.CronJob:
    # Load and render backup script template
    template_path = pathlib.Path(__file__).parent.parent / 'assets' / 'backup.sh.j2'
    template_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_path.parent))
    template = template_env.get_template(template_path.name)

    backup_script_content = template.render(
        retention_daily=component_config.retention_daily,
        retention_weekly=component_config.retention_weekly,
        retention_monthly=component_config.retention_monthly,
        retention_yearly=component_config.retention_yearly,
        volumes=component_config.volumes,
    )

    # ConfigMap with backup script
    backup_script_configmap = k8s.core.v1.ConfigMap(
        'backup-script',
        metadata={'name': 'backup-script'},
        data={'backup.sh': backup_script_content},
        opts=k8s_opts,
    )

    # Secret for restic password
    restic_password_secret = k8s.core.v1.Secret(
        'restic-password',
        metadata={'name': 'restic-password'},
        string_data={
            'restic-password': component_config.restic_password.value,
        },
        opts=k8s_opts,
    )

    # Secret for S3 credentials
    s3_credentials_secret = k8s.core.v1.Secret(
        's3-credentials',
        metadata={'name': 's3-credentials'},
        string_data={
            'AWS_S3_ENDPOINT': component_config.s3.endpoint.value,
            'AWS_ACCESS_KEY_ID': component_config.s3.access_key_id.value,
            'AWS_SECRET_ACCESS_KEY': component_config.s3.secret_access_key.value,
        },
        opts=k8s_opts,
    )

    # Prepare volumes and volume mounts
    volumes: list[k8s.core.v1.VolumeArgsDict] = [
        {
            'name': 'backup-script',
            'config_map': {
                'name': backup_script_configmap.metadata.name,
                'default_mode': 0o755,
            },
        },
        {
            'name': 'restic-password',
            'secret': {
                'secret_name': restic_password_secret.metadata.name,
            },
        },
    ]

    volume_mounts: list[k8s.core.v1.VolumeMountArgsDict] = [
        {
            'name': 'backup-script',
            'mount_path': '/scripts',
            'read_only': True,
        },
        {
            'name': 'restic-password',
            'mount_path': '/secrets',
            'read_only': True,
        },
    ]

    # Add NFS volumes using CSI driver
    for volume_config in component_config.volumes:
        volume_name = f'nfs-{volume_config.name}'
        volumes.append(
            {
                'name': volume_name,
                'csi': {
                    'driver': 'nfs.csi.k8s.io',
                    'volume_attributes': {
                        'server': volume_config.nfs_server,
                        'share': volume_config.nfs_path,
                        'mount_options': volume_config.nfs_mount_options,
                    },
                },
            }
        )

        volume_mounts.append(
            {
                'name': volume_name,
                'mount_path': volume_config.mount_path,
                'read_only': True,
            }
        )

    # Environment variables (non-sensitive only)
    env_vars: list[k8s.core.v1.EnvVarArgsDict] = [
        {
            'name': 'RESTIC_COMPRESSION',
            'value': 'max',
        },
        {
            'name': 'RESTIC_PACK_SIZE',
            'value': '64M',
        },
        # S3 credentials from secret
        {
            'name': 'AWS_S3_ENDPOINT',
            'value_from': {
                'secret_key_ref': {
                    'name': s3_credentials_secret.metadata.name,
                    'key': 'AWS_S3_ENDPOINT',
                },
            },
        },
        {
            'name': 'AWS_ACCESS_KEY_ID',
            'value_from': {
                'secret_key_ref': {
                    'name': s3_credentials_secret.metadata.name,
                    'key': 'AWS_ACCESS_KEY_ID',
                },
            },
        },
        {
            'name': 'AWS_SECRET_ACCESS_KEY',
            'value_from': {
                'secret_key_ref': {
                    'name': s3_credentials_secret.metadata.name,
                    'key': 'AWS_SECRET_ACCESS_KEY',
                },
            },
        },
    ]

    # CronJob for backup
    return k8s.batch.v1.CronJob(
        'backup-cronjob',
        metadata={'name': 'backup-cronjob'},
        spec={
            'schedule': component_config.schedule,
            'job_template': {
                'spec': {
                    'template': {
                        'spec': {
                            'restart_policy': 'OnFailure',
                            'security_context': {
                                'run_as_non_root': True,
                                'run_as_user': 1000,
                                'fs_group': 1000,
                            },
                            'containers': [
                                {
                                    'name': 'backup',
                                    'image': f'restic/restic:{component_config.restic.version}',
                                    'command': ['/bin/sh'],
                                    'args': ['/scripts/backup.sh'],
                                    'env': env_vars,
                                    'volume_mounts': volume_mounts,
                                    'resources': component_config.resources.to_resource_requirements(),
                                }
                            ],
                            'volumes': volumes,
                        },
                    },
                },
            },
        },
        opts=k8s_opts,
    )
