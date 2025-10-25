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

    # Create PersistentVolumes and PersistentVolumeClaims for each persistence share
    pvcs: dict[str, p.Output[str]] = {}
    for share_name, share_config in component_config.immich.persistence.items():
        # Create PersistentVolume for NFS storage
        pv = k8s.core.v1.PersistentVolume(
            f'immich-{share_name}',
            metadata={
                'name': f'immich-{share_name}',
            },
            spec={
                'capacity': {
                    'storage': share_config.size,
                },
                'access_modes': ['ReadWriteMany'],
                'persistent_volume_reclaim_policy': 'Retain',
                'mount_options': share_config.nfs_mount_options.split(','),
                'csi': {
                    'driver': 'nfs.csi.k8s.io',
                    'volume_handle': p.Output.concat(
                        share_config.nfs_server,
                        '#',
                        share_config.nfs_path,
                        '#',
                    ),
                    'volume_attributes': {
                        'server': share_config.nfs_server,
                        'share': share_config.nfs_path,
                    },
                },
            },
            opts=p.ResourceOptions(provider=k8s_provider),
        )

        # Create PersistentVolumeClaim for storage
        pvc = k8s.core.v1.PersistentVolumeClaim(
            f'immich-{share_name}',
            metadata={
                'namespace': namespace,
                'name': f'immich-{share_name}',
            },
            spec={
                'access_modes': ['ReadWriteMany'],
                'storage_class_name': '',  # Use no storage class for static binding
                'volume_name': pv.metadata.name,
                'resources': {
                    'requests': {
                        'storage': share_config.size,
                    },
                },
            },
            opts=p.ResourceOptions(provider=k8s_provider),
        )
        pvcs[share_name] = pvc.metadata.name

    # Build persistence configuration for external libraries
    persistence_values: dict = {
        share_name: {
            'enabled': True,
            'existingClaim': pvc_name,
            'readOnly': True,
        }
        for share_name, pvc_name in pvcs.items()
        if share_name != 'library'
    }

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
                'service': {
                    'main': {
                        'annotations': {
                            'prometheus.io/scrape': 'true',
                            'prometheus.io/port': '8081',
                        },
                        'ports': {
                            'metrics-server': {
                                'enabled': True,
                                'port': '8081',
                            },
                            'metrics-microservices': {
                                'enabled': True,
                                'port': '8082',
                            },
                        },
                    },
                },
                'persistence': persistence_values,
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
                                    # Enable full telemetry
                                    'IMMICH_TELEMETRY_INCLUDE': 'all',
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
                        'existingClaim': pvcs['library'],
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
