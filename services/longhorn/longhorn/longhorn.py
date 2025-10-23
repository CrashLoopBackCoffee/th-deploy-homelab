import base64

import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.unbound.host_override

from longhorn.config import ComponentConfig

LONGHORN_HTTP_PORT = 443


class Longhorn(p.ComponentResource):
    def __init__(self, name: str, component_config: ComponentConfig, k8s_provider: k8s.Provider):
        super().__init__(f'lab:longhorn:{name}', name)

        assert component_config.longhorn
        assert component_config.s3

        # Create namespace for Longhorn (will be used by Helm chart)
        namespace = k8s.core.v1.Namespace(
            'longhorn-system',
            metadata={'name': 'longhorn-system'},
            opts=p.ResourceOptions(provider=k8s_provider, parent=self),
        )

        namespaced_provider = k8s.Provider(
            'longhorn',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace.metadata['name'],
            opts=p.ResourceOptions(parent=self),
        )
        k8s_opts = p.ResourceOptions(provider=namespaced_provider, parent=self)

        # Create S3 backup secret for Longhorn
        # Longhorn expects AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_ENDPOINTS
        secret = k8s.core.v1.Secret(
            'longhorn-s3-secret',
            metadata={
                'namespace': namespace.metadata.name,
                'name': 'longhorn-s3-secret',
            },
            data={
                'AWS_ACCESS_KEY_ID': p.Output.from_input(
                    component_config.s3.access_key_id.value
                ).apply(lambda v: base64.b64encode(v.encode()).decode()),
                'AWS_SECRET_ACCESS_KEY': p.Output.from_input(
                    component_config.s3.secret_access_key.value
                ).apply(lambda v: base64.b64encode(v.encode()).decode()),
                'AWS_ENDPOINTS': p.Output.from_input(component_config.s3.endpoint.value).apply(
                    lambda v: base64.b64encode(v.encode()).decode()
                ),
            },
            opts=k8s_opts,
        )

        # Deploy Longhorn via Helm
        # Using v3.Release because Longhorn chart has post-upgrade and pre-delete hooks
        chart = k8s.helm.v3.Release(
            'longhorn',
            name='longhorn',
            chart='longhorn',
            version=component_config.longhorn.chart_version,
            namespace=namespace.metadata.name,
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo='https://charts.longhorn.io',
            ),
            values={
                'defaultSettings': {
                    # Single-node configuration with 1 replica
                    'defaultReplicaCount': 1,
                    # Use dedicated disk mounted at /var/lib/longhorn
                    'defaultDataPath': '/var/lib/longhorn',
                },
                'defaultBackupStore': {
                    # S3 backup target format: s3://bucket@region/
                    # Region is arbitrary when using custom endpoint (comes from AWS_ENDPOINTS in secret)
                    'backupTarget': 's3://longhorn@us-east-1/',
                    'backupTargetCredentialSecret': secret.metadata.name,
                },
                'persistence': {
                    # Don't set as default storage class - keep microk8s-hostpath as default
                    'defaultClass': False,
                },
                # Enable UI service
                'service': {
                    'ui': {
                        'type': 'ClusterIP',
                    },
                },
            },
            opts=p.ResourceOptions(provider=k8s_provider, parent=self, depends_on=[secret]),
        )

        # Create StorageClass for Longhorn (non-default)
        k8s.storage.v1.StorageClass(
            'longhorn-storageclass',
            metadata={
                'name': 'longhorn',
            },
            provisioner='driver.longhorn.io',
            allow_volume_expansion=True,
            reclaim_policy='Delete',
            volume_binding_mode='Immediate',
            parameters={
                'numberOfReplicas': '1',
                'staleReplicaTimeout': '30',
                'fromBackup': '',
                'fsType': 'ext4',
            },
            opts=p.ResourceOptions(provider=k8s_provider, parent=self, depends_on=[chart]),
        )

        # Create TLS certificate for Longhorn UI (only if hostname is configured)
        if component_config.longhorn.hostname:
            certificate = k8s.apiextensions.CustomResource(
                'certificate',
                api_version='cert-manager.io/v1',
                kind='Certificate',
                metadata={
                    'name': 'longhorn-ui-tls',
                    'namespace': namespace.metadata.name,
                    'annotations': {
                        'pulumi.com/waitFor': 'condition=Ready=True',
                    },
                },
                spec={
                    'secretName': 'longhorn-ui-tls',
                    'issuerRef': {
                        'name': 'lets-encrypt',
                        'kind': 'ClusterIssuer',
                    },
                    'dnsNames': [component_config.longhorn.hostname],
                },
                opts=k8s_opts,
            )

            # Create LoadBalancer service for Longhorn UI with TLS
            service = k8s.core.v1.Service(
                'longhorn-ui-lb',
                metadata={
                    'namespace': namespace.metadata.name,
                    'name': 'longhorn-ui-lb',
                },
                spec={
                    'type': 'LoadBalancer',
                    'selector': {
                        'app': 'longhorn-ui',
                    },
                    'ports': [
                        {
                            'name': 'https',
                            'port': LONGHORN_HTTP_PORT,
                            'target_port': 'http',  # Longhorn UI runs on port 8000
                            'protocol': 'TCP',
                        },
                    ],
                },
                opts=k8s_opts,
            )

            # Create nginx config for TLS termination and proxy to Longhorn UI
            nginx_config = k8s.core.v1.ConfigMap(
                'longhorn-ui-proxy-config',
                metadata={
                    'namespace': namespace.metadata.name,
                    'name': 'longhorn-ui-proxy-config',
                },
                data={
                    'nginx.conf': f"""
events {{
    worker_connections 1024;
}}

http {{
    server {{
        listen {LONGHORN_HTTP_PORT} ssl;
        server_name {component_config.longhorn.hostname};

        ssl_certificate /etc/nginx/certs/tls.crt;
        ssl_certificate_key /etc/nginx/certs/tls.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        location / {{
            proxy_pass http://longhorn-frontend.longhorn-system.svc.cluster.local:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }}
    }}
}}
"""
                },
                opts=k8s_opts,
            )

            # Create a deployment that proxies to the Longhorn UI with TLS termination
            # This is similar to how Alloy exposes its UI
            k8s.apps.v1.Deployment(
                'longhorn-ui-proxy',
                metadata={
                    'namespace': namespace.metadata.name,
                    'name': 'longhorn-ui-proxy',
                },
                spec={
                    'replicas': 1,
                    'selector': {
                        'match_labels': {
                            'app': 'longhorn-ui-proxy',
                        },
                    },
                    'template': {
                        'metadata': {
                            'labels': {
                                'app': 'longhorn-ui-proxy',
                            },
                        },
                        'spec': {
                            'containers': [
                                {
                                    'name': 'nginx',
                                    'image': 'nginx:alpine',
                                    'ports': [
                                        {
                                            'name': 'https',
                                            'container_port': LONGHORN_HTTP_PORT,
                                            'protocol': 'TCP',
                                        },
                                    ],
                                    'volume_mounts': [
                                        {
                                            'name': 'tls-certs',
                                            'mount_path': '/etc/nginx/certs',
                                            'read_only': True,
                                        },
                                        {
                                            'name': 'nginx-config',
                                            'mount_path': '/etc/nginx/nginx.conf',
                                            'sub_path': 'nginx.conf',
                                            'read_only': True,
                                        },
                                    ],
                                    'resources': {
                                        'requests': {
                                            'memory': '64Mi',
                                        },
                                        'limits': {
                                            'memory': '128Mi',
                                        },
                                    },
                                },
                            ],
                            'volumes': [
                                {
                                    'name': 'tls-certs',
                                    'secret': {
                                        'secret_name': certificate.spec.apply(  # type: ignore
                                            lambda spec: spec['secretName']
                                        ),
                                    },
                                },
                                {
                                    'name': 'nginx-config',
                                    'config_map': {
                                        'name': nginx_config.metadata.name,
                                    },
                                },
                            ],
                        },
                    },
                },
                opts=k8s_opts,
            )

            # Update service selector to point to proxy
            service = k8s.core.v1.Service(
                'longhorn-ui-lb',
                metadata={
                    'namespace': namespace.metadata.name,
                    'name': 'longhorn-ui-lb',
                },
                spec={
                    'type': 'LoadBalancer',
                    'selector': {
                        'app': 'longhorn-ui-proxy',
                    },
                    'ports': [
                        {
                            'name': 'https',
                            'port': LONGHORN_HTTP_PORT,
                            'target_port': LONGHORN_HTTP_PORT,
                            'protocol': 'TCP',
                        },
                    ],
                },
                opts=k8s_opts,
            )

            # Get LoadBalancer IP and create local DNS record
            def create_dns_record(args):
                lb_ip = args[0]
                if (
                    lb_ip
                    and lb_ip != ''
                    and component_config.longhorn
                    and component_config.longhorn.hostname
                ):
                    return utils.opnsense.unbound.host_override.HostOverride(
                        'longhorn-host-override',
                        host=component_config.longhorn.hostname.split('.')[0],
                        domain='.'.join(component_config.longhorn.hostname.split('.')[1:]),
                        record_type='A',
                        ipaddress=lb_ip,
                    )
                return None

            service.status.load_balancer.ingress[0].ip.apply(
                lambda ip: create_dns_record([ip]) if ip else None
            )

            # Export outputs
            self.url = p.Output.from_input(f'https://{component_config.longhorn.hostname}')
            self.lb_ip = service.status.load_balancer.ingress[0].ip

        self.register_outputs({})
