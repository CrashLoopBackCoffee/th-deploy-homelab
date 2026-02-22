import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.unbound.host_override

from monitoring.config import ComponentConfig


class Goldilocks(p.ComponentResource):
    def __init__(self, name: str, component_config: ComponentConfig, k8s_provider: k8s.Provider):
        super().__init__(f'lab:goldilocks:{name}', name)

        k8s_opts = p.ResourceOptions(provider=k8s_provider, parent=self)

        namespace = k8s.core.v1.Namespace(
            'goldilocks-namespace',
            metadata={'name': 'goldilocks'},
            opts=k8s_opts,
        )

        chart = k8s.helm.v4.Chart(
            'goldilocks',
            chart='goldilocks',
            version=component_config.goldilocks.version,
            namespace=namespace.metadata.name,
            repository_opts={'repo': 'https://charts.fairwinds.com/stable'},
            values={
                'dashboard': {'enabled': True},
                'vpa': {'enabled': False},
            },
            opts=k8s_opts,
        )

        traefik_service = k8s.core.v1.Service.get(
            'traefik-service', 'traefik/traefik', opts=k8s_opts
        )
        hostname_parts = component_config.goldilocks.hostname.split('.')
        record = utils.opnsense.unbound.host_override.HostOverride(
            'goldilocks',
            host=hostname_parts[0],
            domain='.'.join(hostname_parts[1:]),
            record_type='A',
            ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
            opts=p.ResourceOptions(parent=self),
        )

        fqdn = component_config.goldilocks.hostname
        k8s.apiextensions.CustomResource(
            'goldilocks-ingress',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={
                'name': 'goldilocks',
                'namespace': namespace.metadata.name,
            },
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        'match': p.Output.concat('Host(`', fqdn, '`)'),
                        'services': [
                            {
                                'name': 'goldilocks-dashboard',
                                'namespace': namespace.metadata.name,
                                'port': 80,
                            },
                        ],
                    }
                ],
                'tls': {},
            },
            opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[chart])),
        )

        p.export('goldilocks_url', p.Output.concat('https://', record.host, '.', record.domain))

        self.register_outputs({})
