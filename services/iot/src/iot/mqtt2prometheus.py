import copy

import deploy_base.opnsense.unbound.host_override
import pulumi as p
import pulumi_kubernetes as k8s
import yaml

from iot.config import ComponentConfig

EXPORTER_PORT = 9641


class Mqtt2Prometheus(p.ComponentResource):
    def __init__(self, name: str, component_config: ComponentConfig, k8s_provider: k8s.Provider):
        if not component_config.mqtt2prometheus or not component_config.mqtt2prometheus.instances:
            return

        super().__init__(f'lab:mqtt2prometheus:{name}', name)

        namespace = k8s.core.v1.Namespace(
            'mqtt2prometheus',
            metadata={'name': 'mqtt2prometheus'},
            opts=p.ResourceOptions(provider=k8s_provider, parent=self),
        )

        k8s_provider = k8s.Provider(
            'mqtt2prometheus',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace.metadata['name'],
            opts=p.ResourceOptions(parent=self),
        )
        k8s_opts = p.ResourceOptions(provider=k8s_provider, parent=self)

        base_config = {
            'mqtt': {
                'server': f'mqtts://{component_config.mosquitto.hostname}:8883',
                'qos': 0,
            },
            'cache': {
                'timeout': '60m',
            },
            'json_parsing': {'separator': '.'},
        }

        mqtt_credentials = k8s.core.v1.Secret(
            'mqtt-credentials',
            string_data={
                'username': component_config.mqtt2prometheus.username.value,
                'password': component_config.mqtt2prometheus.password.value,
            },
            opts=k8s_opts,
        )

        for instance in component_config.mqtt2prometheus.instances:
            pvc = k8s.core.v1.PersistentVolumeClaim(
                f'mosquitto-{instance.name}',
                metadata={'name': f'mosquitto-{instance.name}'},
                spec={
                    'access_modes': ['ReadWriteOnce'],
                    'resources': {'requests': {'storage': '1Gi'}},
                },
                opts=k8s_opts,
            )

            config = copy.deepcopy(base_config)
            config['mqtt']['topic_path'] = instance.topic_path
            config['mqtt']['client_id'] = f'mqtt2prometheus-{instance.name}'
            config['metrics'] = instance.metrics
            if instance.device_id_regex:
                config['mqtt']['device_id_regex'] = instance.device_id_regex

            config_map = k8s.core.v1.ConfigMap(
                f'mqtt2prometheus-config-{instance.name}',
                data={'config.yaml': yaml.safe_dump(config)},
                opts=k8s_opts,
            )

            app_labels = {'app': f'mqtt2prometheus-{instance.name}'}
            deployment = k8s.apps.v1.Deployment(
                f'mqtt2prometheus-{instance.name}',
                metadata={'namespace': namespace.metadata['name']},
                spec={
                    'replicas': 1,
                    'selector': {'match_labels': app_labels},
                    'template': {
                        'metadata': {'labels': app_labels},
                        'spec': {
                            'containers': [
                                {
                                    'name': 'mqtt2prometheus',
                                    'image': f'ghcr.io/hikhvar/mqtt2prometheus:{component_config.mqtt2prometheus.version}',
                                    'env': [
                                        {
                                            'name': 'MQTT2PROM_MQTT_USER',
                                            'value_from': {
                                                'secret_key_ref': {
                                                    'name': mqtt_credentials.metadata.name,
                                                    'key': 'username',
                                                }
                                            },
                                        },
                                        {
                                            'name': 'MQTT2PROM_MQTT_PASSWORD',
                                            'value_from': {
                                                'secret_key_ref': {
                                                    'name': mqtt_credentials.metadata.name,
                                                    'key': 'password',
                                                }
                                            },
                                        },
                                    ],
                                    'ports': [
                                        {'container_port': EXPORTER_PORT, 'name': 'exporter'},
                                    ],
                                    'volume_mounts': [
                                        {
                                            'name': 'config',
                                            'mount_path': '/config.yaml',
                                            'sub_path': 'config.yaml',
                                            'read_only': True,
                                        },
                                        {
                                            'name': 'data',
                                            'mount_path': '/var/lib/mqtt2prometheus',
                                        },
                                    ],
                                }
                            ],
                            'volumes': [
                                {
                                    'name': 'data',
                                    'persistent_volume_claim': {'claim_name': pvc.metadata.name},
                                },
                                {
                                    'name': 'config',
                                    'config_map': {'name': config_map.metadata.name},
                                },
                            ],
                        },
                    },
                },
                opts=k8s_opts,
            )

            service = k8s.core.v1.Service(
                f'mqtt2prometheus-{instance.name}',
                metadata={'name': f'mqtt2promehteus-{instance.name}'},
                spec={
                    'selector': deployment.spec.selector['match_labels'],
                    'ports': [{'port': EXPORTER_PORT, 'target_port': 'exporter'}],
                    # TODO: Use ClusterIP when Alloy is in the cluster
                    'type': 'LoadBalancer',
                },
                opts=k8s_opts,
            )

            # Create local DNS record
            record = deploy_base.opnsense.unbound.host_override.HostOverride(
                f'mqtt2prometheus-{instance.name}',
                host=f'{instance.name}',
                domain='mqtt2prometheus.local',
                record_type='A',
                ipaddress=service.status.apply(lambda x: x['load_balancer']['ingress'][0]['ip']),  # type: ignore
            )

            p.export(
                f'mqtt2prometheus-{instance.name}',
                p.Output.format(
                    '{}.{}:{}',
                    record.host,
                    record.domain,
                    EXPORTER_PORT,
                ),
            )
