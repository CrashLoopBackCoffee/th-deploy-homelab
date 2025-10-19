import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.unbound.host_override
import utils.postgres

from immich.config import ComponentConfig

IMMICH_PORT = 2283


def create_immich(
    component_config: ComponentConfig,
    namespace: p.Input[str],
    k8s_provider: k8s.Provider,
    postgres_db: utils.postgres.PostgresDatabase,
):
    """
    Deploy Immich photo management service using official Helm chart
    """
    assert component_config.immich

    namespaced_provider = k8s.Provider(
        'immich-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace,
    )
    k8s_opts = p.ResourceOptions(
        provider=namespaced_provider,
    )

    # Create PersistentVolume for NFS library storage
    pv = k8s.core.v1.PersistentVolume(
        'immich-library',
        metadata={
            'name': 'immich-library',
        },
        spec={
            'capacity': {
                'storage': '100Gi',
            },
            'access_modes': ['ReadWriteMany'],
            'persistent_volume_reclaim_policy': 'Retain',
            'mount_options': component_config.immich.library_mount_options.split(','),
            'csi': {
                'driver': 'nfs.csi.k8s.io',
                'volume_handle': p.Output.concat(
                    component_config.immich.library_server,
                    '#',
                    component_config.immich.library_share,
                    '#',
                ),
                'volume_attributes': {
                    'server': component_config.immich.library_server,
                    'share': component_config.immich.library_share,
                },
            },
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    # Create PersistentVolumeClaim for library storage
    library_pvc = k8s.core.v1.PersistentVolumeClaim(
        'immich-library',
        metadata={
            'namespace': namespace,
            'name': 'immich-library',
        },
        spec={
            'access_modes': ['ReadWriteMany'],
            'storage_class_name': '',  # Use no storage class for static binding
            'volume_name': pv.metadata.name,
            'resources': {
                'requests': {
                    'storage': '100Gi',
                },
            },
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    # Deploy Immich using official Helm chart
    chart = k8s.helm.v4.Chart(
        'immich',
        chart='oci://ghcr.io/immich-app/immich-charts/immich',
        namespace=namespace,
        version=component_config.immich.chart_version,
        values={
            'controllers': {
                'main': {
                    'containers': {
                        'main': {
                            'image': {
                                'tag': f'v{component_config.immich.version}',
                            },
                        },
                    },
                },
            },
            'server': {
                'controllers': {
                    'main': {
                        'containers': {
                            'main': {
                                'env': {
                                    'DB_HOSTNAME': {
                                        'valueFrom': {
                                            'secretKeyRef': {
                                                'name': postgres_db.secret_name,
                                                'key': 'host',
                                            }
                                        }
                                    },
                                    'DB_PORT': {
                                        'valueFrom': {
                                            'secretKeyRef': {
                                                'name': postgres_db.secret_name,
                                                'key': 'port',
                                            }
                                        }
                                    },
                                    'DB_DATABASE_NAME': {
                                        'valueFrom': {
                                            'secretKeyRef': {
                                                'name': postgres_db.secret_name,
                                                'key': 'dbname',
                                            }
                                        }
                                    },
                                    'DB_USERNAME': {
                                        'valueFrom': {
                                            'secretKeyRef': {
                                                'name': postgres_db.superuser_secret_name,
                                                'key': 'username',
                                            }
                                        }
                                    },
                                    'DB_PASSWORD': {
                                        'valueFrom': {
                                            'secretKeyRef': {
                                                'name': postgres_db.superuser_secret_name,
                                                'key': 'password',
                                            }
                                        }
                                    },
                                },
                            },
                        },
                    },
                },
            },
            'valkey': {
                'enabled': True,
                'auth': {
                    'enabled': False,
                },
            },
            'immich': {
                'persistence': {
                    'library': {
                        'enabled': True,
                        'existingClaim': library_pvc.metadata.name,
                    },
                },
            },
            'machine-learning': {
                'persistence': {
                    'cache': {
                        'enabled': True,
                        'size': '10Gi',
                        'type': 'persistentVolumeClaim',
                    },
                },
            },
        },
        opts=p.ResourceOptions(provider=namespaced_provider),
    )

    immich_service = k8s.core.v1.Service.get(
        'immich-server',
        p.Output.concat(namespace, '/immich-server'),
        opts=p.ResourceOptions(
            provider=k8s_provider,
            depends_on=chart.resources,  # pyright: ignore[reportArgumentType]
        ),
    )

    # Create local DNS record pointing to Traefik service
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    record = utils.opnsense.unbound.host_override.HostOverride(
        'immich',
        host='immich',
        domain=component_config.cloudflare.zone,
        record_type='A',
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )

    # Create IngressRoute for internal access
    fqdn = p.Output.concat('immich.', component_config.cloudflare.zone)
    k8s.apiextensions.CustomResource(
        'ingress',
        api_version='traefik.io/v1alpha1',
        kind='IngressRoute',
        metadata={
            'name': 'ingress',
            'namespace': namespace,
        },
        spec={
            'entryPoints': ['websecure'],
            'routes': [
                {
                    'kind': 'Rule',
                    'match': p.Output.concat('Host(`', fqdn, '`)'),
                    'services': [
                        {
                            'name': immich_service.metadata.name,
                            'namespace': immich_service.metadata.namespace,
                            'port': IMMICH_PORT,
                        },
                    ],
                }
            ],
            'tls': {},
        },
        opts=k8s_opts,
    )

    p.export(
        'immich_url',
        p.Output.concat('https://', record.host, '.', record.domain),
    )
