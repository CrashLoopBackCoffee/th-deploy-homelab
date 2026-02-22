import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.unbound.host_override

from monitoring.config import ComponentConfig
from monitoring.utils import get_assets_path

ALLOY_HTTP_PORT = 443
ALLOY_OTEL_GRPC_PORT = 4317
ALLOY_OTEL_HTTP_PORT = 4318

GRAFANA_CLOUD_USER_KEY = 'GRAFANA_CLOUD_API_USER'
GRAFANA_CLOUD_TOKEN_KEY = 'GRAFANA_CLOUD_API_TOKEN'


class Alloy(p.ComponentResource):
    def __init__(self, name: str, component_config: ComponentConfig, k8s_provider: k8s.Provider):
        super().__init__(f'lab:alloy:{name}', name)

        namespace = k8s.core.v1.Namespace(
            'alloy',
            metadata={
                'name': 'alloy',
                'labels': {'goldilocks.fairwinds.com/enabled': 'true'},
            },
            opts=p.ResourceOptions(provider=k8s_provider, parent=self),
        )

        namespaced_provider = k8s.Provider(
            'alloy',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace.metadata['name'],
            opts=p.ResourceOptions(parent=self),
        )
        k8s_opts = p.ResourceOptions(provider=namespaced_provider, parent=self)

        # Create data volume
        pvc = k8s.core.v1.PersistentVolumeClaim(
            'alloy-data',
            metadata={
                'namespace': namespace.metadata.name,
                'name': 'alloy-data',
            },
            spec={
                'access_modes': ['ReadWriteOnce'],
                'resources': {
                    'requests': {
                        'storage': '1Gi',
                    },
                },
            },
            opts=k8s_opts,
        )

        # Create Secret with Grafana Cloud credentials
        secret = k8s.core.v1.Secret(
            'alloy-secrets',
            metadata={
                'namespace': namespace.metadata.name,
            },
            string_data={
                GRAFANA_CLOUD_USER_KEY: component_config.grafana_cloud.username,
                GRAFANA_CLOUD_TOKEN_KEY: str(component_config.grafana_cloud.token),
            },
            opts=k8s_opts,
        )

        # Create ConfigMap with Alloy configuration
        alloy_config_files = {}
        alloy_path = get_assets_path() / 'alloy'
        for config_file in alloy_path.glob('*.alloy'):
            alloy_config_files[config_file.name] = config_file.read_text()

        config_map = k8s.core.v1.ConfigMap(
            'alloy-config',
            metadata={
                'namespace': namespace.metadata.name,
            },
            data=alloy_config_files,
            opts=k8s_opts,
        )

        # Create ConfigMap with SNMP configuration
        snmp_config_path = get_assets_path().parent / 'assets' / 'snmp' / 'snmp.yml'
        snmp_config_map = k8s.core.v1.ConfigMap(
            'alloy-snmp-config',
            metadata={
                'namespace': namespace.metadata.name,
            },
            data={
                'snmp.yml': snmp_config_path.read_text(),
            },
            opts=k8s_opts,
        )

        # Create ServiceAccount for Alloy
        service_account = k8s.core.v1.ServiceAccount(
            'alloy-serviceaccount',
            metadata={
                'name': 'alloy',
                'namespace': namespace.metadata.name,
            },
            opts=k8s_opts,
        )

        # Create ClusterRole with permissions to access Kubernetes resources for log collection
        cluster_role = k8s.rbac.v1.ClusterRole(
            'alloy-clusterrole',
            metadata={'name': 'alloy'},
            rules=[
                {
                    'api_groups': [''],
                    'resources': [
                        'pods',
                        'pods/log',
                        'nodes',
                        'nodes/proxy',
                        'nodes/metrics',
                        'services',
                        'endpoints',
                    ],
                    'verbs': ['get', 'list', 'watch'],
                },
                {
                    'api_groups': [''],
                    'resources': ['events'],
                    'verbs': ['get', 'list', 'watch'],
                },
                {
                    'api_groups': [''],
                    'resources': ['namespaces'],
                    'verbs': ['get', 'list', 'watch'],
                },
                {
                    'api_groups': ['monitoring.coreos.com'],
                    'resources': ['podmonitors', 'servicemonitors'],
                    'verbs': ['get', 'list', 'watch'],
                },
            ],
            opts=p.ResourceOptions(provider=k8s_provider, parent=self),
        )

        # Create ClusterRoleBinding
        k8s.rbac.v1.ClusterRoleBinding(
            'alloy-clusterrolebinding',
            metadata={'name': 'alloy'},
            role_ref={
                'api_group': 'rbac.authorization.k8s.io',
                'kind': 'ClusterRole',
                'name': cluster_role.metadata.name,
            },
            subjects=[
                {
                    'kind': 'ServiceAccount',
                    'name': service_account.metadata.name,
                    'namespace': namespace.metadata.name,
                },
            ],
            opts=p.ResourceOptions(provider=k8s_provider, parent=self),
        )

        # Create TLS certificate
        certificate = k8s.apiextensions.CustomResource(
            'certificate',
            api_version='cert-manager.io/v1',
            kind='Certificate',
            metadata={
                'name': 'alloy-tls',
                'namespace': namespace.metadata.name,
                'annotations': {
                    'pulumi.com/waitFor': 'condition=Ready=True',
                },
            },
            spec={
                'secretName': 'alloy-tls',
                'issuerRef': {
                    'name': 'lets-encrypt',
                    'kind': 'ClusterIssuer',
                },
                'dnsNames': [component_config.alloy.hostname],
            },
            opts=k8s_opts,
        )

        # Create Alloy deployment
        app_labels = {'app': 'alloy'}
        deployment = k8s.apps.v1.Deployment(
            'alloy',
            metadata={
                'namespace': namespace.metadata.name,
                'name': 'alloy',
            },
            spec={
                'replicas': 1,
                'selector': {
                    'match_labels': app_labels,
                },
                'template': {
                    'metadata': {
                        'labels': app_labels,
                    },
                    'spec': {
                        'service_account_name': service_account.metadata.name,
                        'containers': [
                            {
                                'name': 'alloy',
                                'image': f'grafana/alloy:{component_config.alloy.version}',
                                'args': [
                                    'run',
                                    f'--server.http.listen-addr=0.0.0.0:{ALLOY_HTTP_PORT}',
                                    '--storage.path=/var/lib/alloy/data',
                                    '--disable-reporting',
                                    '--stability.level=experimental',
                                    '/etc/alloy/',
                                ],
                                'ports': [
                                    {
                                        'name': 'http',
                                        'container_port': ALLOY_HTTP_PORT,
                                        'protocol': 'TCP',
                                    },
                                    {
                                        'name': 'otel-grpc',
                                        'container_port': ALLOY_OTEL_GRPC_PORT,
                                        'protocol': 'TCP',
                                    },
                                    {
                                        'name': 'otel-http',
                                        'container_port': ALLOY_OTEL_HTTP_PORT,
                                        'protocol': 'TCP',
                                    },
                                    {
                                        'name': 'syslog',
                                        'container_port': 514,
                                        'protocol': 'UDP',
                                    },
                                ],
                                'env_from': [
                                    {
                                        'secret_ref': {
                                            'name': secret.metadata.name,
                                        },
                                    },
                                ],
                                'volume_mounts': [
                                    {
                                        'name': 'config',
                                        'mount_path': '/etc/alloy',
                                    },
                                    {
                                        'name': 'snmp-config',
                                        'mount_path': '/etc/alloy/snmp',
                                    },
                                    {
                                        'name': 'data',
                                        'mount_path': '/var/lib/alloy/data',
                                    },
                                    {
                                        'name': 'tls-certs',
                                        'mount_path': '/etc/alloy/certs',
                                    },
                                    {
                                        'name': 'var-log',
                                        'mount_path': '/var/log',
                                        'read_only': True,
                                    },
                                    {
                                        'name': 'var-log-pods',
                                        'mount_path': '/var/log/pods',
                                        'read_only': True,
                                    },
                                ],
                                'resources': {
                                    'requests': {
                                        'memory': '256Mi',
                                    },
                                    'limits': {
                                        'memory': '512Mi',
                                    },
                                },
                                'readiness_probe': {
                                    'http_get': {
                                        'path': '/-/ready',
                                        'port': ALLOY_HTTP_PORT,
                                        'scheme': 'HTTPS',
                                    },
                                    'initial_delay_seconds': 10,
                                    'period_seconds': 10,
                                    'timeout_seconds': 5,
                                    'success_threshold': 1,
                                    'failure_threshold': 3,
                                },
                            },
                        ],
                        'volumes': [
                            {
                                'name': 'config',
                                'config_map': {
                                    'name': config_map.metadata.name,
                                },
                            },
                            {
                                'name': 'snmp-config',
                                'config_map': {
                                    'name': snmp_config_map.metadata.name,
                                },
                            },
                            {
                                'name': 'data',
                                'persistent_volume_claim': {
                                    'claim_name': pvc.metadata.name,
                                },
                            },
                            {
                                'name': 'tls-certs',
                                'secret': {
                                    'secret_name': certificate.spec.apply(  # type: ignore
                                        lambda spec: spec['secretName']
                                    ),
                                },
                            },
                            {
                                'name': 'var-log',
                                'host_path': {
                                    'path': '/var/log',
                                    'type': 'Directory',
                                },
                            },
                            {
                                'name': 'var-log-pods',
                                'host_path': {
                                    'path': '/var/log/pods',
                                    'type': 'DirectoryOrCreate',
                                },
                            },
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        # Create LoadBalancer service
        service = k8s.core.v1.Service(
            'alloy',
            metadata={
                'namespace': namespace.metadata.name,
                'name': 'alloy',
            },
            spec={
                'type': 'LoadBalancer',
                'selector': deployment.spec.selector.match_labels,
                'ports': [
                    {
                        'name': 'http',
                        'port': ALLOY_HTTP_PORT,
                        'target_port': ALLOY_HTTP_PORT,
                        'protocol': 'TCP',
                    },
                    {
                        'name': 'otel-grpc',
                        'port': ALLOY_OTEL_GRPC_PORT,
                        'target_port': ALLOY_OTEL_GRPC_PORT,
                        'protocol': 'TCP',
                    },
                    {
                        'name': 'otel-http',
                        'port': ALLOY_OTEL_HTTP_PORT,
                        'target_port': ALLOY_OTEL_HTTP_PORT,
                        'protocol': 'TCP',
                    },
                    {
                        'name': 'syslog',
                        'port': 514,
                        'target_port': 514,
                        'protocol': 'UDP',
                    },
                ],
            },
            opts=k8s_opts,
        )

        # Get LoadBalancer IP and create local DNS record
        def create_dns_record(args):
            lb_ip = args[0]
            if lb_ip and lb_ip != '' and component_config.alloy and component_config.alloy.hostname:
                utils.opnsense.unbound.host_override.HostOverride(
                    'alloy-host-override',
                    host=component_config.alloy.hostname.split('.')[0],
                    domain='.'.join(component_config.alloy.hostname.split('.')[1:]),
                    record_type='A',
                    ipaddress=lb_ip,
                )

        service.status.load_balancer.ingress[0].ip.apply(
            lambda ip: create_dns_record([ip]) if ip else None
        )

        # Export outputs
        self.url = p.Output.from_input(f'https://{component_config.alloy.hostname}')
        self.lb_ip = service.status.load_balancer.ingress[0].ip

        p.export('alloy_url', self.url)
        p.export('alloy_lb_ip', self.lb_ip)
