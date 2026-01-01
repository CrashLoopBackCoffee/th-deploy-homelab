import pathlib

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig
from monitoring.mimir_buckets import MimirBuckets


class Mimir(p.ComponentResource):
    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        cloudflare_provider: cloudflare.Provider,
        mimir_buckets: MimirBuckets,
        k8s_provider: k8s.Provider,
    ):
        super().__init__(f'lab:mimir:{name}', name)

        k8s_opts = p.ResourceOptions(provider=k8s_provider, parent=self)

        # Create namespace
        namespace = k8s.core.v1.Namespace(
            'mimir-namespace',
            metadata={'name': 'mimir'},
            opts=k8s_opts,
        )

        # Load mimir config template
        config_path = pathlib.Path(__file__).parent.parent / 'assets' / 'mimir' / 'config.yaml'
        with open(config_path, 'r', encoding='UTF-8') as f:
            mimir_config_content = f.read()

        # Create ConfigMap for mimir configuration
        config_map = k8s.core.v1.ConfigMap(
            'mimir-config',
            metadata={
                'namespace': namespace.metadata.name,
            },
            data={'config.yaml': mimir_config_content},
            opts=k8s_opts,
        )

        # Get S3 configuration
        s3_config = p.Config().require_object('s3')

        # Create secret for sensitive S3 credentials
        mimir_secret = k8s.core.v1.Secret(
            'mimir-secret',
            metadata={
                'namespace': namespace.metadata.name,
            },
            string_data={
                'aws-access-key-id': mimir_buckets.bucket_user.name,
                'aws-secret-access-key': mimir_buckets.bucket_user.secret,
            },
            opts=k8s_opts,
        )

        # Pre-create PVCs for StatefulSet following the pattern from:
        # https://github.com/kubernetes/kubernetes/issues/128459#issuecomment-2449557592
        # This gives Pulumi direct control over PVC lifecycle

        # PVC for ingester data
        pvc_data = k8s.core.v1.PersistentVolumeClaim(
            'mimir-data-mimir-0',
            metadata={
                'name': 'mimir-data-mimir-0',
                'namespace': namespace.metadata.name,
            },
            spec={
                'access_modes': ['ReadWriteOnce'],
                'resources': {'requests': {'storage': '50Gi'}},
            },
            opts=k8s_opts,
        )

        app_labels = {'app': 'mimir'}

        # Create StatefulSet with volumeClaimTemplates that reference pre-created PVCs
        # The volumeClaimTemplate spec is intentionally empty to prevent auto-creation
        k8s.apps.v1.StatefulSet(
            'mimir',
            metadata={
                'name': 'mimir',
                'namespace': namespace.metadata.name,
            },
            spec={
                'service_name': 'mimir',
                'replicas': 1,
                'selector': {'match_labels': app_labels},
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        'security_context': {
                            'fs_group': 10001,
                            'run_as_group': 10001,
                            'run_as_non_root': True,
                            'run_as_user': 10001,
                            'seccomp_profile': {'type': 'RuntimeDefault'},
                        },
                        'containers': [
                            {
                                'name': 'mimir',
                                'image': f'grafana/mimir:{component_config.mimir.version}',
                                'args': [
                                    '--config.file=/etc/mimir/config.yaml',
                                    '--config.expand-env=true',
                                ],
                                'env': [
                                    {
                                        'name': 'AWS_ACCESS_KEY_ID',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': mimir_secret.metadata.name,
                                                'key': 'aws-access-key-id',
                                            },
                                        },
                                    },
                                    {
                                        'name': 'AWS_SECRET_ACCESS_KEY',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': mimir_secret.metadata.name,
                                                'key': 'aws-secret-access-key',
                                            },
                                        },
                                    },
                                    {'name': 'MINIO_HOSTNAME', 'value': s3_config['endpoint']},
                                    {
                                        'name': 'MINIO_BUCKET_ALERTMANAGER',
                                        'value': mimir_buckets.bucket_alertmanager.bucket,
                                    },
                                    {
                                        'name': 'MINIO_BUCKET_BLOCKS',
                                        'value': mimir_buckets.bucket_blocks.bucket,
                                    },
                                    {
                                        'name': 'MINIO_BUCKET_RULER',
                                        'value': mimir_buckets.bucket_ruler.bucket,
                                    },
                                ],
                                'ports': [
                                    {'name': 'http', 'container_port': 9009},
                                    {'name': 'grpc', 'container_port': 9095},
                                ],
                                'volume_mounts': [
                                    {
                                        'name': 'mimir-data',
                                        'mount_path': '/data',
                                    },
                                    {
                                        'name': 'config',
                                        'mount_path': '/etc/mimir',
                                        'read_only': True,
                                    },
                                ],
                                'resources': {
                                    'requests': {
                                        'memory': '2Gi',
                                        'cpu': '500m',
                                    },
                                },
                                'security_context': {
                                    'allow_privilege_escalation': False,
                                    'read_only_root_filesystem': True,
                                    'capabilities': {'drop': ['ALL']},
                                },
                            },
                        ],
                        'volumes': [
                            {
                                'name': 'config',
                                'config_map': {'name': config_map.metadata.name},
                            },
                        ],
                    },
                },
                'volume_claim_templates': [
                    {
                        'metadata': {'name': 'mimir-data'},
                        # Spec without storage resource requests to avoid auto-creation
                        # The StatefulSet will use the pre-created PVC named mimir-data-mimir-0
                        'spec': {
                            'access_modes': ['ReadWriteOnce'],
                            'resources': {
                                'requests': {'storage': '1Gi'},
                            },
                            'storage_class_name': 'fake',
                        },
                    },
                ],
            },
            opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[pvc_data])),
        )

        # Create headless service for StatefulSet
        k8s.core.v1.Service(
            'mimir-headless',
            metadata={
                'name': 'mimir-headless',
                'namespace': namespace.metadata.name,
            },
            spec={
                'cluster_ip': 'None',
                'ports': [
                    {'name': 'http', 'port': 9009, 'target_port': 9009},
                    {'name': 'grpc', 'port': 9095, 'target_port': 9095},
                ],
                'selector': app_labels,
            },
            opts=k8s_opts,
        )

        # Create regular service for external access
        service = k8s.core.v1.Service(
            'mimir-service',
            metadata={
                'name': 'mimir',
                'namespace': namespace.metadata.name,
            },
            spec={
                'type': 'ClusterIP',
                'ports': [
                    {'name': 'http', 'port': 9009, 'target_port': 9009},
                    {'name': 'grpc', 'port': 9095, 'target_port': 9095},
                ],
                'selector': app_labels,
            },
            opts=k8s_opts,
        )

        self.namespace = namespace.metadata.name
        self.service_name = service.metadata.name
        self.service_port = 9009

        self.register_outputs(
            {
                'namespace': self.namespace,
                'service_name': self.service_name,
                'service_port': self.service_port,
            }
        )
