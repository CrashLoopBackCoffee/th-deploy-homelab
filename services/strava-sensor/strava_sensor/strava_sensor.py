import pulumi as p
import pulumi_kubernetes as k8s

from strava_sensor.config import ComponentConfig

STRAVA_SENSOR_PORT = 8000
STRAVA_SENSOR_STATE_PATH = '/app/local_state'
ALLOY_OTEL_GRPC_ENDPOINT = 'http://alloy.alloy.cluster.svc.local:4317'


def create_strava_sensor(component_config: ComponentConfig, k8s_provider: k8s.Provider) -> None:
    """
    Deploy Strava Sensor webhook listener.
    """
    strava_sensor = component_config.strava_sensor

    k8s_opts = p.ResourceOptions(provider=k8s_provider)
    namespace = k8s.core.v1.Namespace(
        'strava-sensor',
        metadata={'name': 'strava-sensor'},
        opts=k8s_opts,
    )

    secret_data: dict[str, p.Input[str]] = {
        'strava-refresh-token': strava_sensor.strava.refresh_token.value,
        'strava-client-id': strava_sensor.strava.client_id.value,
        'strava-client-secret': strava_sensor.strava.client_secret.value,
        'mqtt-username': strava_sensor.mqtt.username.value,
        'mqtt-password': strava_sensor.mqtt.password.value,
    }

    if strava_sensor.garmin:
        secret_data['garmin-username'] = strava_sensor.garmin.username.value
        secret_data['garmin-password'] = strava_sensor.garmin.password.value

    secret = k8s.core.v1.Secret(
        'strava-sensor',
        metadata={'namespace': namespace.metadata.name},
        type='Opaque',
        string_data=secret_data,
        opts=k8s_opts,
    )

    pvc = k8s.core.v1.PersistentVolumeClaim(
        'strava-sensor-state',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'strava-sensor-state',
        },
        spec={
            'access_modes': ['ReadWriteOnce'],
            'resources': {'requests': {'storage': strava_sensor.storage.state_size}},
        },
        opts=k8s_opts,
    )

    env_vars: list[k8s.core.v1.EnvVarArgsDict] = [
        {
            'name': 'STRAVA_REFRESH_TOKEN',
            'value_from': {
                'secret_key_ref': {
                    'name': secret.metadata.name,
                    'key': 'strava-refresh-token',
                }
            },
        },
        {
            'name': 'STRAVA_CLIENT_ID',
            'value_from': {
                'secret_key_ref': {
                    'name': secret.metadata.name,
                    'key': 'strava-client-id',
                }
            },
        },
        {
            'name': 'STRAVA_CLIENT_SECRET',
            'value_from': {
                'secret_key_ref': {
                    'name': secret.metadata.name,
                    'key': 'strava-client-secret',
                }
            },
        },
        {
            'name': 'STRAVA_WEBHOOK_URL',
            'value': strava_sensor.webhook_url,
        },
        {
            'name': 'MQTT_BROKER_URL',
            'value': strava_sensor.mqtt.broker_url,
        },
        {
            'name': 'MQTT_USERNAME',
            'value_from': {
                'secret_key_ref': {
                    'name': secret.metadata.name,
                    'key': 'mqtt-username',
                }
            },
        },
        {
            'name': 'MQTT_PASSWORD',
            'value_from': {
                'secret_key_ref': {
                    'name': secret.metadata.name,
                    'key': 'mqtt-password',
                }
            },
        },
        {
            'name': 'OTEL_EXPORTER_OTLP_ENDPOINT',
            'value': ALLOY_OTEL_GRPC_ENDPOINT,
        },
        {
            'name': 'OTEL_EXPORTER_OTLP_PROTOCOL',
            'value': 'grpc',
        },
        {
            'name': 'OTEL_EXPORTER_OTLP_INSECURE',
            'value': 'true',
        },
        {
            'name': 'OTEL_SERVICE_NAME',
            'value': 'strava-sensor',
        },
    ]

    if strava_sensor.webhook_registration_delay is not None:
        env_vars.append(
            {
                'name': 'STRAVA_WEBHOOK_REGISTRATION_DELAY',
                'value': str(strava_sensor.webhook_registration_delay),
            }
        )

    if strava_sensor.garmin:
        env_vars.extend(
            [
                {
                    'name': 'GARMIN_USERNAME',
                    'value_from': {
                        'secret_key_ref': {
                            'name': secret.metadata.name,
                            'key': 'garmin-username',
                        }
                    },
                },
                {
                    'name': 'GARMIN_PASSWORD',
                    'value_from': {
                        'secret_key_ref': {
                            'name': secret.metadata.name,
                            'key': 'garmin-password',
                        }
                    },
                },
            ]
        )

    app_labels = {'app': 'strava-sensor'}
    statefulset = k8s.apps.v1.StatefulSet(
        'strava-sensor',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'strava-sensor',
        },
        spec={
            'replicas': 1,
            'service_name': 'strava-sensor',
            'selector': {'match_labels': app_labels},
            'template': {
                'metadata': {'labels': app_labels},
                'spec': {
                    'containers': [
                        {
                            'name': 'strava-sensor',
                            'image': f'ghcr.io/crashloopbackcoffee/th-strava-sensor:{strava_sensor.version}',
                            'ports': [
                                {'name': 'http', 'container_port': STRAVA_SENSOR_PORT},
                            ],
                            'env': env_vars,
                            'resources': {
                                'requests': {
                                    'memory': strava_sensor.resources.memory,
                                    'cpu': strava_sensor.resources.cpu,
                                },
                            },
                            'volume_mounts': [
                                {
                                    'name': 'state',
                                    'mount_path': STRAVA_SENSOR_STATE_PATH,
                                },
                            ],
                            'readiness_probe': {
                                'http_get': {
                                    'path': '/',
                                    'port': STRAVA_SENSOR_PORT,
                                },
                                'period_seconds': 10,
                                'timeout_seconds': 5,
                            },
                        }
                    ],
                    'volumes': [
                        {
                            'name': 'state',
                            'persistent_volume_claim': {
                                'claim_name': pvc.metadata.name,
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    k8s.core.v1.Service(
        'strava-sensor',
        metadata={
            'namespace': namespace.metadata.name,
            'name': 'strava-sensor',
        },
        spec={
            'ports': [
                {
                    'name': 'http',
                    'port': STRAVA_SENSOR_PORT,
                    'target_port': 'http',
                }
            ],
            'selector': statefulset.spec.selector.match_labels,
        },
        opts=k8s_opts,
    )
