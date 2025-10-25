import json
import textwrap

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.opnsense.unbound.host_override

from utils.postgres import PostgresDatabase

from paperless.backup import create_backup_cronjob
from paperless.config import ComponentConfig

REDIS_PORT = 6379
PAPERLESS_PORT = 8000
TIKA_PORT = 9998
GOTENBERG_PORT = 3000


class Paperless(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('paperless', 'paperless')

        cnpg_database = PostgresDatabase(
            'postgres-paperless',
            component_config.postgres.version,
            namespace,
            k8s_provider,
        )

        admin_username = 'admin'
        admin_password = random.RandomPassword('admin-password', length=32, special=False).result
        p.export('admin_username', admin_username)
        p.export('admin_password', admin_password)
        namespaced_provider = k8s.Provider(
            'paperless-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(
            parent=self,
            provider=namespaced_provider,
        )
        redis_service = create_redis(component_config, k8s_opts)
        tika_service = create_tika(component_config, k8s_opts)
        gotenberg_service = create_gotenberg(component_config, k8s_opts)

        env_vars = {
            'PAPERLESS_REDIS': p.Output.format(
                'redis://{}:{}',
                redis_service.metadata.name,
                REDIS_PORT,
            ),
            'PAPERLESS_CONSUMER_POLLING': '30',
            'PAPERLESS_TASK_WORKERS': '4',
            'PAPERLESS_THREADS_PER_WORKER': '4',
            # Extend the polling delay to account for HP bitch iteratively updating its PDFs after
            # scanning each page.
            'PAPERLESS_CONSUMER_POLLING_DELAY': '30',
            # Wait up to 10min for the scan to finish
            'PAPERLESS_CONSUMER_POLLING_RETRY_COUNT': '20',
            'PAPERLESS_URL': f'https://paperless.{component_config.cloudflare.zone}',
            # https://docs.paperless-ngx.com/troubleshooting/#gunicorn-fails-to-start-with-is-not-a-valid-port-number
            'PAPERLESS_PORT': str(PAPERLESS_PORT),
            'PAPERLESS_ADMIN_USER': admin_username,
            'PAPERLESS_OCR_LANGUAGE': 'deu+eng',
            # Authentication
            'PAPERLESS_APPS': ','.join(
                (
                    'allauth.socialaccount.providers.google',
                    'allauth.socialaccount.providers.openid_connect',
                )
            ),
            'PAPERLESS_ACCOUNT_EMAIL_VERIFICATION': 'none',
            'PAPERLESS_OIDC_DEFAULT_GROUP': 'readers',
            'PAPERLESS_DBENGINE': 'postgresql',
            'PAPERLESS_CONSUMER_ENABLE_BARCODES': 'true',
            'PAPERLESS_CONSUMER_ENABLE_ASN_BARCODE': 'true',
            'PAPERLESS_CONSUMER_BARCODE_SCANNER': 'ZXING',
            'PAPERLESS_CONSUMER_RECURSIVE': 'true',
            'PAPERLESS_CONSUMER_IGNORE_PATTERNS': json.dumps(
                [
                    '._*',
                    '.DS_Store',
                    '.DS_STORE',
                    '.localized/*',
                    '.stfolder/*',
                    '.stversions/*',
                    '@eaDir/*',
                    '#recycle/*',
                    'desktop.ini',
                    'Thumbs.db',
                ]
            ),
            'PAPERLESS_TIKA_ENABLED': 'true',
            'PAPERLESS_TIKA_ENDPOINT': p.Output.format(
                'http://{}:{}', tika_service.metadata.name, TIKA_PORT
            ),
            'PAPERLESS_TIKA_GOTENBERG_ENDPOINT': p.Output.format(
                'http://{}:{}', gotenberg_service.metadata.name, GOTENBERG_PORT
            ),
            'PAPERLESS_GMAIL_OAUTH_CLIENT_ID': component_config.mail.client_id,
            'PAPERLESS_WEBSERVER_WORKERS': '4',
        }

        config_secret = k8s.core.v1.Secret(
            'paperless-config',
            string_data={
                'PAPERLESS_SECRET_KEY': random.RandomPassword(
                    'paperless-secret-key', length=64, special=False
                ).result,
                'PAPERLESS_ADMIN_PASSWORD': admin_password,
                'PAPERLESS_SOCIALACCOUNT_PROVIDERS': p.Output.json_dumps(
                    {
                        'google': {
                            'APPS': [
                                {
                                    'client_id': component_config.google.client_id,
                                    'secret': component_config.google.client_secret,
                                    'key': '',
                                    'settings': {
                                        # You can fine tune these settings per app:
                                        'scope': [
                                            'profile',
                                            'email',
                                        ],
                                        'auth_params': {
                                            'access_type': 'online',
                                        },
                                    },
                                },
                            ],
                            'SCOPE': [
                                'profile',
                                'email',
                            ],
                            'AUTH_PARAMS': {
                                'access_type': 'online',
                            },
                        },
                        'openid_connect': {
                            'APPS': [
                                {
                                    'provider_id': 'microsoft',
                                    'name': 'Microsoft Entra ID',
                                    'client_id': component_config.entraid.client_id,
                                    'secret': component_config.entraid.client_secret,
                                    'settings': {
                                        'server_url': p.Output.concat(
                                            'https://login.microsoftonline.com/',
                                            component_config.entraid.tenant_id,
                                            '/v2.0',
                                        ),
                                        'authorization_url': p.Output.concat(
                                            'https://login.microsoftonline.com/',
                                            component_config.entraid.tenant_id,
                                            '/oauth2/v2.0/authorize',
                                        ),
                                        'access_token_url': p.Output.concat(
                                            'https://login.microsoftonline.com/',
                                            component_config.entraid.tenant_id,
                                            '/oauth2/v2.0/token',
                                        ),
                                        'userinfo_url': 'https://graph.microsoft.com/oidc/userinfo',
                                        'jwks_uri': p.Output.concat(
                                            'https://login.microsoftonline.com/',
                                            component_config.entraid.tenant_id,
                                            '/discovery/v2.0/keys',
                                        ),
                                        'scope': ['openid', 'email', 'profile'],
                                        'extra_data': ['email', 'name', 'preferred_username'],
                                    },
                                }
                            ]
                        },
                    }
                ),
                'PAPERLESS_GMAIL_OAUTH_CLIENT_SECRET': str(component_config.mail.client_secret),
            },
            opts=k8s_opts,
        )

        # Generate rclone config dynamically
        rclone_config = p.Output.format(
            textwrap.dedent("""\
                [gdrive]
                type = drive
                client_id = {0}
                client_secret = {1}
                scope = drive
                token = {{"access_token":"{2}","token_type":"Bearer","refresh_token":"{3}","expiry":"{4}"}}
                root_folder_id = {5}
                """),
            component_config.backup.google_drive.client_id.value,
            component_config.backup.google_drive.client_secret.value,
            component_config.backup.google_drive.access_token.value,
            component_config.backup.google_drive.refresh_token.value,
            component_config.backup.google_drive.token_expiry,
            component_config.backup.google_drive.root_folder_id,
        )

        backup_secret = k8s.core.v1.Secret(
            'paperless-backup-secrets',
            string_data={
                'restic-password': component_config.backup.restic_password.value,
                'rclone.conf': rclone_config,
            },
            opts=k8s_opts,
        )

        app_labels = {'app': 'paperless'}
        sts = k8s.apps.v1.StatefulSet(
            'paperless',
            metadata={'name': 'paperless'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': app_labels},
                'service_name': 'paperless-headless',
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        'init_containers': [
                            {
                                'name': 'setup-rclone-config',
                                'image': 'alpine:latest',
                                'command': ['/bin/sh'],
                                'args': [
                                    '-c',
                                    textwrap.dedent("""\
                                        set -e
                                        echo "Setting up writable rclone config..."
                                        mkdir -p /rclone-config
                                        cp /rclone-config-source/rclone.conf /rclone-config/rclone.conf
                                        chmod 644 /rclone-config/rclone.conf
                                        echo "Writable rclone config ready"
                                        """),
                                ],
                                'volume_mounts': [
                                    {
                                        'name': 'rclone-config-source',
                                        'mount_path': '/rclone-config-source',
                                        'read_only': True,
                                    },
                                    {
                                        'name': 'rclone-config-writable',
                                        'mount_path': '/rclone-config',
                                    },
                                ],
                            },
                        ],
                        'containers': [
                            {
                                'name': 'paperless',
                                'image': f'ghcr.io/paperless-ngx/paperless-ngx:{component_config.paperless.version}',
                                'env': [
                                    *[{'name': k, 'value': v} for k, v in env_vars.items()],
                                    {
                                        'name': 'PAPERLESS_DBPASS',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': cnpg_database.secret_name,
                                                'key': 'password',
                                            },
                                        },
                                    },
                                    {
                                        'name': 'PAPERLESS_DBHOST',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': cnpg_database.secret_name,
                                                'key': 'host',
                                            },
                                        },
                                    },
                                    {
                                        'name': 'PAPERLESS_DBPORT',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': cnpg_database.secret_name,
                                                'key': 'port',
                                            },
                                        },
                                    },
                                    {
                                        'name': 'PAPERLESS_DBNAME',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': cnpg_database.secret_name,
                                                'key': 'dbname',
                                            },
                                        },
                                    },
                                    {
                                        'name': 'PAPERLESS_DBUSER',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': cnpg_database.secret_name,
                                                'key': 'username',
                                            },
                                        },
                                    },
                                ],
                                'env_from': [
                                    {
                                        'secret_ref': {
                                            'name': config_secret.metadata.name,
                                        },
                                    },
                                ],
                                'ports': [{'container_port': PAPERLESS_PORT}],
                                'volume_mounts': [
                                    {
                                        'name': 'data',
                                        'mount_path': '/usr/src/paperless/data',
                                    },
                                    {
                                        'name': 'media',
                                        'mount_path': '/usr/src/paperless/media',
                                    },
                                    {
                                        'name': 'consume',
                                        'mount_path': '/usr/src/paperless/consume',
                                    },
                                    {
                                        'name': 'export',
                                        'mount_path': '/usr/src/paperless/export',
                                    },
                                ],
                            },
                            {
                                'name': 'restic',
                                'image': f'ghcr.io/crashloopbackcoffee/restic-rclone:{component_config.backup.restic_rclone_version}',
                                'command': ['/bin/sh'],
                                'args': ['-c', 'sleep infinity'],
                                'env': [
                                    {
                                        'name': 'RESTIC_REPOSITORY',
                                        'value': f'rclone:gdrive:{component_config.backup.repository_path}',
                                    },
                                    {
                                        'name': 'RESTIC_PASSWORD',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': backup_secret.metadata.name,
                                                'key': 'restic-password',
                                            }
                                        },
                                    },
                                    {
                                        'name': 'RCLONE_CONFIG',
                                        'value': '/rclone-config/rclone.conf',
                                    },
                                ],
                                'volume_mounts': [
                                    {
                                        'name': 'export',
                                        'mount_path': '/usr/src/paperless/export',
                                        'read_only': True,
                                    },
                                    {
                                        'name': 'rclone-config-writable',
                                        'mount_path': '/rclone-config',
                                    },
                                ],
                            },
                            # Optional secondary restic sidecar for IDrive E2 (S3-compatible)
                            *(
                                [
                                    {
                                        'name': 'restic-idrive',
                                        'image': f'ghcr.io/crashloopbackcoffee/restic-rclone:{component_config.backup.restic_rclone_version}',
                                        'command': ['/bin/sh'],
                                        'args': ['-c', 'sleep infinity'],
                                        'env': [
                                            *(
                                                [
                                                    {
                                                        'name': 'RESTIC_REPOSITORY',
                                                        'value': p.Output.from_input(
                                                            component_config.backup.idrive_endpoint.value
                                                        ).apply(
                                                            lambda ep: (
                                                                f's3:{ep if ep.startswith("http") else "https://" + ep}/'
                                                                f'{component_config.backup.idrive_bucket}/'
                                                                f'{component_config.backup.repository_path}'
                                                            )
                                                        ),
                                                    }
                                                ]
                                                if component_config.backup.idrive_endpoint
                                                and component_config.backup.idrive_bucket
                                                else []
                                            ),
                                            {
                                                'name': 'RESTIC_PASSWORD',
                                                'value_from': {
                                                    'secret_key_ref': {
                                                        'name': backup_secret.metadata.name,
                                                        'key': 'restic-password',
                                                    }
                                                },
                                            },
                                            *(
                                                [
                                                    {
                                                        'name': 'AWS_ACCESS_KEY_ID',
                                                        'value': component_config.backup.idrive_access_key_id.value,
                                                    },
                                                    {
                                                        'name': 'AWS_SECRET_ACCESS_KEY',
                                                        'value': component_config.backup.idrive_secret_access_key.value,
                                                    },
                                                ]
                                                if component_config.backup.idrive_access_key_id
                                                and component_config.backup.idrive_secret_access_key
                                                else []
                                            ),
                                            {
                                                'name': 'RESTIC_PROGRESS_FPS',
                                                'value': '0',
                                            },
                                        ],
                                        'volume_mounts': [
                                            {
                                                'name': 'export',
                                                'mount_path': '/usr/src/paperless/export',
                                                'read_only': True,
                                            },
                                        ],
                                    }
                                ]
                                if component_config.backup.idrive_enabled
                                else []
                            ),
                        ],
                        'volumes': [
                            {
                                'name': 'consume',
                                'csi': {
                                    'driver': 'nfs.csi.k8s.io',
                                    'volume_attributes': {
                                        'server': component_config.paperless.consume_server,
                                        'share': component_config.paperless.consume_share,
                                        'mount_options': component_config.paperless.consume_mount_options,
                                    },
                                },
                            },
                            {
                                'name': 'rclone-config-source',
                                'secret': {
                                    'secret_name': backup_secret.metadata.name,
                                },
                            },
                            {
                                'name': 'rclone-config-writable',
                                'empty_dir': {},
                            },
                        ],
                        'security_context': {
                            'fs_group': 1000,
                        },
                    },
                },
                'volume_claim_templates': [
                    {
                        'metadata': {'name': 'data'},
                        'spec': {
                            'access_modes': ['ReadWriteOnce'],
                            'resources': {'requests': {'storage': '100Gi'}},
                        },
                    },
                    {
                        'metadata': {'name': 'media'},
                        'spec': {
                            'access_modes': ['ReadWriteOnce'],
                            'resources': {'requests': {'storage': '100Gi'}},
                        },
                    },
                    {
                        'metadata': {'name': 'export'},
                        'spec': {
                            'access_modes': ['ReadWriteOnce'],
                            'resources': {'requests': {'storage': '100Gi'}},
                        },
                    },
                ],
            },
            opts=k8s_opts,
        )

        service_paperless = k8s.core.v1.Service(
            'paperless',
            metadata={'name': 'paperless'},
            spec={
                'ports': [{'port': PAPERLESS_PORT}],
                'selector': sts.spec.selector.match_labels,
            },
            opts=k8s_opts,
        )

        # Create local DNS record
        traefic_service = k8s.core.v1.Service.get(
            'traefik-service', 'traefik/traefik', opts=k8s_opts
        )
        record = utils.opnsense.unbound.host_override.HostOverride(
            'paperless',
            host='paperless',
            domain=component_config.cloudflare.zone,
            record_type='A',
            ipaddress=traefic_service.status.load_balancer.ingress[0].ip,
        )

        fqdn = f'paperless.{component_config.cloudflare.zone}'
        k8s.apiextensions.CustomResource(
            'ingress',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={
                'name': 'ingress',
            },
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        'match': p.Output.concat('Host(`', fqdn, '`)'),
                        'services': [
                            {
                                'name': service_paperless.metadata.name,
                                'namespace': service_paperless.metadata.namespace,
                                'port': PAPERLESS_PORT,
                            },
                        ],
                    }
                ],
                # use default wildcard certificate:
                'tls': {},
            },
            opts=k8s_opts,
        )

        p.export(
            'paperless_url',
            p.Output.format('https://{}.{}', record.host, record.domain),
        )

        # Create backup CronJob
        create_backup_cronjob(component_config, k8s_opts)

        self.register_outputs({})


def create_redis(component_config: ComponentConfig, opts: p.ResourceOptions) -> k8s.core.v1.Service:
    app_labels_redis = {'app': 'redis'}
    redis_sts = k8s.apps.v1.StatefulSet(
        'redis',
        metadata={'name': 'redis'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_redis},
            'service_name': 'redis-headless',
            'template': {
                'metadata': {'labels': app_labels_redis},
                'spec': {
                    'containers': [
                        {
                            'name': 'redis',
                            'image': f'docker.io/library/redis:{component_config.redis.version}',
                            'ports': [{'container_port': REDIS_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'redis',
        metadata={'name': 'redis'},
        spec={
            'ports': [{'port': REDIS_PORT}],
            'selector': redis_sts.spec.selector.match_labels,
        },
        opts=opts,
    )


def create_tika(component_config: ComponentConfig, opts: p.ResourceOptions) -> k8s.core.v1.Service:
    app_labels_tika = {'app': 'tika'}
    tika_sts = k8s.apps.v1.Deployment(
        'tika',
        metadata={'name': 'tika'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_tika},
            'template': {
                'metadata': {'labels': app_labels_tika},
                'spec': {
                    'containers': [
                        {
                            'name': 'tika',
                            'image': f'docker.io/apache/tika:{component_config.tika.version}',
                            'ports': [{'container_port': TIKA_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'tika',
        metadata={'name': 'tika'},
        spec={
            'ports': [{'port': TIKA_PORT}],
            'selector': tika_sts.spec.selector.match_labels,
        },
        opts=opts,
    )


def create_gotenberg(
    component_config: ComponentConfig, opts: p.ResourceOptions
) -> k8s.core.v1.Service:
    app_labels_gotenberg = {'app': 'gotenberg'}
    gotenberg_sts = k8s.apps.v1.Deployment(
        'gotenberg',
        metadata={'name': 'gotenberg'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_gotenberg},
            'template': {
                'metadata': {'labels': app_labels_gotenberg},
                'spec': {
                    'containers': [
                        {
                            'name': 'gotenberg',
                            'image': f'docker.io/gotenberg/gotenberg:{component_config.gotenberg.version}',
                            # The gotenberg chromium route is used to convert .eml files. We do not
                            # want to allow external content like tracking pixels or even javascript.
                            'command': [
                                'gotenberg',
                                '--chromium-disable-javascript=true',
                                '--chromium-allow-list=file:///tmp/.*',
                            ],
                            'ports': [{'container_port': GOTENBERG_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'gotenberg',
        metadata={'name': 'gotenberg'},
        spec={
            'ports': [{'port': GOTENBERG_PORT}],
            'selector': gotenberg_sts.spec.selector.match_labels,
        },
        opts=opts,
    )
