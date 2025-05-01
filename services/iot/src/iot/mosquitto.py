import textwrap

import deploy_base
import deploy_base.opnsense.unbound.host_override
import pulumi as p
import pulumi_kubernetes as k8s

from iot.config import ComponentConfig

MOSQUITTO_CONFIG = textwrap.dedent(
    """\
    persistence true
    persistence_location /mosquitto/data/
    log_dest stdout

    password_file /mosquitto/config/password.txt

    # MQTTS listener
    listener 8883
    protocol mqtt
    cafile /etc/ssl/certs/ca-certificates.crt
    keyfile /mosquitto/certs/tls.key
    certfile /mosquitto/certs/tls.crt
    """
)


MQTT_PORT = 8883


class Mosquitto(p.ComponentResource):
    def __init__(self, name: str, component_config: ComponentConfig, k8s_provider: k8s.Provider):
        super().__init__(f'lab:mosquitto:{name}', name)

        namespace = k8s.core.v1.Namespace(
            'mosquitto',
            metadata={'name': 'mosquitto'},
            opts=p.ResourceOptions(provider=k8s_provider, parent=self),
        )

        namespaced_provider = k8s.Provider(
            'mosquitto',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace.metadata['name'],
            opts=p.ResourceOptions(parent=self),
        )
        k8s_opts = p.ResourceOptions(provider=namespaced_provider, parent=self)

        certificate = k8s.apiextensions.CustomResource(
            'certificate',
            api_version='cert-manager.io/v1',
            kind='Certificate',
            metadata={'name': 'mosquitto'},
            spec={
                'secretName': 'mosquitto-tls',
                'dnsNames': [component_config.mosquitto.hostname],
                'issuerRef': {'name': 'lets-encrypt', 'kind': 'ClusterIssuer'},
            },
            opts=k8s_opts,
        )

        config = k8s.core.v1.ConfigMap(
            'mosquitto-config',
            data={'mosquitto.conf': MOSQUITTO_CONFIG},
            opts=k8s_opts,
        )

        password = k8s.core.v1.ConfigMap(
            'mosquitto-password',
            data={
                # Generated via mosquitto_passwd using op://Pulumi/Mosquitto/password
                'password.txt': '\n'.join(component_config.mosquitto.passwords),
            },
            opts=k8s_opts,
        )

        pvc = k8s.core.v1.PersistentVolumeClaim(
            'mosquitto',
            metadata={'name': 'mosquitto'},
            spec={
                'access_modes': ['ReadWriteOnce'],
                'resources': {'requests': {'storage': '1Gi'}},
            },
            opts=k8s_opts,
        )

        app_labels = {'app': 'mosquitto'}
        deployment = k8s.apps.v1.Deployment(
            'mosquitto',
            metadata={'labels': app_labels, 'name': 'mosquitto'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': app_labels},
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        'containers': [
                            {
                                'name': 'mosquitto',
                                'image': f'eclipse-mosquitto:{component_config.mosquitto.version}',
                                'ports': [
                                    {'container_port': MQTT_PORT, 'name': 'mqtts'},
                                ],
                                'volume_mounts': [
                                    {'name': 'certs', 'mount_path': '/mosquitto/certs/'},
                                    {'name': 'data', 'mount_path': '/mosquitto/data/'},
                                    {
                                        'name': 'config',
                                        'mount_path': '/mosquitto/config/mosquitto.conf',
                                        'sub_path': 'mosquitto.conf',
                                        'read_only': True,
                                    },
                                    {
                                        'name': 'password',
                                        'mount_path': '/mosquitto/config/password.txt',
                                        'sub_path': 'password.txt',
                                        'read_only': True,
                                    },
                                ],
                            }
                        ],
                        'security_context': {
                            'fs_group': 1883,
                            'run_as_non_root': True,
                            'run_as_user': 1883,
                        },
                        'volumes': [
                            {
                                'name': 'certs',
                                'secret': {
                                    'secret_name': certificate.spec.apply(  # type: ignore
                                        lambda x: x['secretName']
                                    ),
                                    'default_mode': 0o600,
                                },
                            },
                            {
                                'name': 'data',
                                'persistent_volume_claim': {'claim_name': pvc.metadata.name},
                            },
                            {
                                'name': 'config',
                                'config_map': {'name': config.metadata.name},
                            },
                            {
                                'name': 'password',
                                'config_map': {
                                    'name': password.metadata.name,
                                    'default_mode': 0o600,
                                },
                            },
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        service = k8s.core.v1.Service(
            'mosquitto-mqtts',
            metadata={'name': 'mosquitto-mqtts'},
            spec={
                'type': 'LoadBalancer',
                'ports': [{'port': MQTT_PORT, 'target_port': 'mqtts'}],
                'selector': deployment.spec.apply(lambda x: x['selector']['match_labels']),
                'external_traffic_policy': 'Local',
            },
            opts=k8s_opts,
        )

        deploy_base.opnsense.unbound.host_override.HostOverride(
            'mosquitto',
            host=component_config.mosquitto.hostname.split('.')[0],
            domain=component_config.mosquitto.hostname.split('.', 1)[1],
            record_type='A',
            ipaddress=service.status.apply(lambda x: x['load_balancer']['ingress'][0]['ip']),  # type: ignore
        )

        p.export(
            'mqtts_address',
            service.status.apply(lambda x: x['load_balancer']['ingress'][0]['ip']),  # type: ignore
        )
        p.export('mqtts_port', MQTT_PORT)
        p.export('mqtts_hostname', component_config.mosquitto.hostname)
