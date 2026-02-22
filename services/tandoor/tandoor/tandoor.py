import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.opnsense.unbound.host_override
import utils.postgres

from tandoor.config import ComponentConfig

TANDOOR_PORT = 80  # Tandoor 2 uses nginx on port 80


def create_tandoor(component_config: ComponentConfig, k8s_provider: k8s.Provider) -> None:
    """
    Deploy Tandoor Recipes application
    """
    assert component_config.tandoor

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'tandoor',
        metadata={
            'name': 'tandoor',
        },
        opts=k8s_opts,
    )

    # Create postgres database using CloudNativePG
    postgres_db = utils.postgres.PostgresDatabase(
        'postgres',
        postgres_version=component_config.postgres.version,
        namespace_name=namespace.metadata.name,
        k8s_provider=k8s_provider,
        backup_enabled=component_config.postgres.backup is not None,
        backup_config=component_config.postgres.backup,
    )

    # Create secret key for Django
    secret_key = random.RandomPassword(
        'tandoor-secret-key',
        length=50,
        special=True,
        upper=True,
        lower=True,
        numeric=True,
    )

    # Create Kubernetes secret for sensitive data
    secret = k8s.core.v1.Secret(
        'tandoor-secret',
        metadata={
            'namespace': namespace.metadata.name,
        },
        type='Opaque',
        string_data={
            'secret-key': secret_key.result,
        },
        opts=k8s_opts,
    )

    app_labels = {'app': 'tandoor'}

    # Create PersistentVolumeClaims
    staticfiles_pvc = k8s.core.v1.PersistentVolumeClaim(
        'staticfiles',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'staticfiles',
        },
        spec={
            'access_modes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': '5Gi'}},
        },
        opts=k8s_opts,
    )

    mediafiles_pvc = k8s.core.v1.PersistentVolumeClaim(
        'mediafiles',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'mediafiles',
        },
        spec={
            'access_modes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': '10Gi'}},
        },
        opts=k8s_opts,
    )

    # Create Deployment
    deployment = k8s.apps.v1.Deployment(
        'tandoor',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'tandoor',
            'labels': app_labels,
        },
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels},
            'strategy': {
                'type': 'Recreate',
            },
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'security_context': {
                        'fs_group': 65534,  # Set filesystem group to nobody
                    },
                    'init_containers': [
                        {
                            'name': 'init-db-and-static',
                            'image': f'vabene1111/recipes:{component_config.tandoor.version}',
                            'command': ['sh', '-c'],
                            'args': [
                                """
                                set -e
                                source venv/bin/activate
                                echo "Updating database"
                                python manage.py migrate
                                echo "Collecting static files"
                                python manage.py collectstatic --noinput
                                echo "Done"
                                """
                            ],
                            'env': [
                                {
                                    'name': 'SECRET_KEY',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': secret.metadata.name,
                                            'key': 'secret-key',
                                        }
                                    },
                                },
                                {
                                    'name': 'DB_ENGINE',
                                    'value': 'django.db.backends.postgresql',
                                },
                                {
                                    'name': 'POSTGRES_HOST',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'host',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_PORT',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'port',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_DB',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'dbname',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_USER',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'username',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_PASSWORD',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'password',
                                        }
                                    },
                                },
                                {
                                    'name': 'TANDOOR_PORT',
                                    'value': '80',  # Override Kubernetes auto-injected service variable
                                },
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'staticfiles',
                                    'mount_path': '/opt/recipes/staticfiles',
                                },
                                {
                                    'name': 'mediafiles',
                                    'mount_path': '/opt/recipes/mediafiles',
                                },
                            ],
                        },
                    ],
                    'containers': [
                        {
                            'name': 'tandoor',
                            'image': f'vabene1111/recipes:{component_config.tandoor.version}',
                            'ports': [{'name': 'http', 'container_port': TANDOOR_PORT}],
                            'env': [
                                {
                                    'name': 'SECRET_KEY',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': secret.metadata.name,
                                            'key': 'secret-key',
                                        }
                                    },
                                },
                                {
                                    'name': 'DB_ENGINE',
                                    'value': 'django.db.backends.postgresql',
                                },
                                {
                                    'name': 'POSTGRES_HOST',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'host',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_PORT',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'port',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_DB',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'dbname',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_USER',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'username',
                                        }
                                    },
                                },
                                {
                                    'name': 'POSTGRES_PASSWORD',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': postgres_db.secret_name,
                                            'key': 'password',
                                        }
                                    },
                                },
                                {
                                    'name': 'ALLOWED_HOSTS',
                                    'value': component_config.tandoor.hostname,
                                },
                                {
                                    'name': 'TZ',
                                    'value': 'Europe/Berlin',
                                },
                                {
                                    'name': 'TANDOOR_PORT',
                                    'value': '80',  # Override Kubernetes auto-injected service variable
                                },
                                {
                                    'name': 'GUNICORN_MEDIA',
                                    'value': '0',  # Disable gunicorn media serving (nginx handles it)
                                },
                            ],
                            'volume_mounts': [
                                {
                                    'name': 'staticfiles',
                                    'mount_path': '/opt/recipes/staticfiles',
                                },
                                {
                                    'name': 'mediafiles',
                                    'mount_path': '/opt/recipes/mediafiles',
                                },
                            ],
                            'resources': component_config.tandoor.resources.to_resource_requirements(),
                        },
                    ],
                    'volumes': [
                        {
                            'name': 'staticfiles',
                            'persistent_volume_claim': {
                                'claim_name': staticfiles_pvc.metadata.name
                            },
                        },
                        {
                            'name': 'mediafiles',
                            'persistent_volume_claim': {'claim_name': mediafiles_pvc.metadata.name},
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    # Create Service
    service = k8s.core.v1.Service(
        'tandoor',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'tandoor',
        },
        spec={
            'ports': [{'name': 'http', 'port': TANDOOR_PORT}],
            'selector': deployment.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )

    # Create local DNS record
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'tandoor',
        host='tandoor',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # Create IngressRoute for internal access
    fqdn = f'tandoor.{component_config.cloudflare.zone}'
    k8s.apiextensions.CustomResource(
        'ingress',
        api_version='traefik.io/v1alpha1',
        kind='IngressRoute',
        metadata={
            'name': 'ingress',
            'namespace': namespace.metadata.name,
        },
        spec={
            'entryPoints': ['websecure'],
            'routes': [
                {
                    'kind': 'Rule',
                    'match': p.Output.concat('Host(`', fqdn, '`)'),
                    'middlewares': [
                        {
                            'name': 'tandoor-headers',
                            'namespace': namespace.metadata.name,
                        }
                    ],
                    'services': [
                        {
                            'name': service.metadata.name,
                            'namespace': service.metadata.namespace,
                            'port': TANDOOR_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    # Create middleware for required headers
    k8s.apiextensions.CustomResource(
        'tandoor-headers',
        api_version='traefik.io/v1alpha1',
        kind='Middleware',
        metadata={
            'name': 'tandoor-headers',
            'namespace': namespace.metadata.name,
        },
        spec={
            'headers': {
                'customRequestHeaders': {
                    'X-Forwarded-Proto': 'https',
                },
            },
        },
        opts=k8s_opts,
    )

    p.export(
        'tandoor_url',
        p.Output.format('https://{}.{}', record.host, record.domain),
    )
