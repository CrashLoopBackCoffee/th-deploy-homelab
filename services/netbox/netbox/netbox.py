import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_minio as minio
import pulumi_random as random
import utils.postgres
import yaml

from netbox.config import ComponentConfig

CNPG_APP_DB_NAME = 'app'


class Netbox(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ) -> None:
        super().__init__('netbox', 'netbox')

        cnpg_database = utils.postgres.PostgresDatabase(
            'postgres-netbox',
            namespace,
            k8s_provider,
            postgres_version=component_config.postgres.version,
        )

        namespaced_provider = k8s.Provider(
            'netbox-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore[reportUnknownMemberType]
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(
            parent=self,
            provider=namespaced_provider,
        )

        admin_password = random.RandomPassword(
            'netbox-admin-password',
            length=32,
            special=False,
        ).result
        admin_api_token = random.RandomId(
            'netbox-admin-api-token',
            byte_length=20,
        ).hex
        secret_key = random.RandomPassword(
            'netbox-secret-key',
            length=64,
            special=False,
        ).result
        api_token_pepper = random.RandomPassword(
            'netbox-api-token-pepper',
            length=64,
            special=False,
        ).result

        superuser_secret = k8s.core.v1.Secret(
            'netbox-superuser',
            type='kubernetes.io/basic-auth',
            string_data={
                'username': component_config.netbox.superuser.name,
                'password': admin_password,
                'email': component_config.netbox.superuser.email,
                'api_token': admin_api_token,
            },
            opts=k8s_opts,
        )

        config_secret = k8s.core.v1.Secret(
            'netbox-config',
            string_data={
                'email_password': '',
                'secret_key': secret_key,
            },
            opts=k8s_opts,
        )

        api_token_pepper_secret = k8s.core.v1.Secret(
            'netbox-api-token-pepper',
            string_data={
                'api-token-peppers.yaml': api_token_pepper.apply(
                    lambda v: yaml.safe_dump(
                        {
                            'API_TOKEN_PEPPERS': {
                                1: v,
                            }
                        }
                    )
                )
            },
            opts=k8s_opts,
        )

        s3_config = p.Config().require_object('s3')
        minio_opts = p.ResourceOptions(
            provider=minio.Provider(
                'minio',
                minio_server=f'{s3_config["endpoint"]}:443',
                minio_user=s3_config['admin-user'],
                minio_password=p.Output.secret(s3_config['admin-password']),
                minio_ssl=True,
                opts=p.ResourceOptions(parent=self),
            ),
            parent=self,
        )

        bucket_media = minio.S3Bucket(
            'netbox-media',
            bucket='netbox-media',
            opts=minio_opts,
        )

        bucket_policy = minio.IamPolicy(
            'netbox',
            policy=p.Output.json_dumps(
                {
                    'Version': '2012-10-17',
                    'Statement': [
                        {
                            'Action': ['s3:ListBucket'],
                            'Effect': 'Allow',
                            'Resource': [bucket_media.arn],
                        },
                        {
                            'Action': ['s3:*'],
                            'Effect': 'Allow',
                            'Resource': [p.Output.format('{}/*', bucket_media.arn)],
                        },
                    ],
                }
            ),
            opts=minio_opts,
        )

        bucket_user = minio.IamUser(
            'netbox',
            opts=minio_opts,
        )

        minio.IamUserPolicyAttachment(
            'netbox',
            user_name=bucket_user.name,
            policy_name=bucket_policy.name,
            opts=minio_opts,
        )

        s3_storage_config = p.Output.json_dumps(
            {
                'STORAGES': {
                    'default': {
                        'BACKEND': 'storages.backends.s3.S3Storage',
                        'OPTIONS': {
                            'bucket_name': bucket_media.bucket,
                            'endpoint_url': f'https://{s3_config["endpoint"]}',
                            'access_key': bucket_user.name,
                            'secret_key': bucket_user.secret,
                        },
                    },
                    'static': {
                        'BACKEND': 'django.core.files.storage.FileSystemStorage',
                        'OPTIONS': {
                            'location': '/opt/netbox/netbox/static',
                        },
                    },
                }
            }
        )

        s3_secret = k8s.core.v1.Secret(
            'netbox-s3-config',
            metadata={'name': 'netbox-s3-config'},
            string_data={
                's3.yaml': s3_storage_config,
            },
            opts=k8s_opts,
        )

        affinity = {
            'podAffinity': {
                'requiredDuringSchedulingIgnoredDuringExecution': [
                    {
                        'labelSelector': {
                            'matchLabels': {
                                'app.kubernetes.io/name': 'netbox',
                            }
                        },
                        'topologyKey': 'kubernetes.io/hostname',
                    }
                ]
            }
        }

        values = {
            'replicaCount': 1,
            'resourcesPreset': 'none',
            'superuser': {
                'existingSecret': superuser_secret.metadata.name,
            },
            'existingSecret': config_secret.metadata.name,
            'ingress': {
                'enabled': False,
            },
            'httpRoute': {
                'enabled': False,
            },
            'persistence': {
                'enabled': False,
            },
            'reportsPersistence': {
                'enabled': False,
            },
            'scriptsPersistence': {
                'enabled': False,
            },
            'affinity': affinity,
            'worker': {
                'replicaCount': 1,
                'resourcesPreset': 'none',
                'affinity': affinity,
            },
            'housekeeping': {
                'resourcesPreset': 'none',
                'affinity': affinity,
            },
            'postgresql': {
                'enabled': False,
            },
            'externalDatabase': {
                'host': 'postgres-netbox-rw',
                'port': 5432,
                'database': CNPG_APP_DB_NAME,
                'username': CNPG_APP_DB_NAME,
                'existingSecretName': cnpg_database.secret_name,
                'existingSecretKey': 'password',
            },
            'valkey': {
                'architecture': 'standalone',
                'primary': {
                    'persistence': {
                        'size': component_config.netbox.storage.valkey_size,
                    }
                },
                'replica': {
                    'replicaCount': 0,
                },
            },
            'extraConfig': [
                {
                    'secret': {
                        'secretName': s3_secret.metadata.name,
                    }
                },
                {
                    'secret': {
                        'secretName': api_token_pepper_secret.metadata.name,
                    }
                },
            ],
        }

        k8s.helm.v4.Chart(
            'netbox',
            chart='oci://ghcr.io/netbox-community/netbox-chart/netbox',
            version=component_config.netbox.chart_version,
            namespace=namespace,
            values=values,
            opts=k8s_opts,
        )

        p.export('netbox_admin_username', component_config.netbox.superuser.name)
        p.export('netbox_admin_password', admin_password)
        p.export('netbox_admin_api_token', admin_api_token)

        self.register_outputs({})
