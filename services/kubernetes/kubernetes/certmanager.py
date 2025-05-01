import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_certmanager(
    component_config: ComponentConfig,
    cloudflare_provider: cloudflare.Provider,
    k8s_provider: k8s.Provider,
) -> k8s.apiextensions.CustomResource:
    namespace = k8s.core.v1.Namespace(
        'cert-manager',
        metadata={'name': 'cert-manager'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'cert-manager-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Note we use Release instead of Chart in order to have one resource instead of 25
    chart = k8s.helm.v3.Release(
        'cert-manager',
        chart='cert-manager',
        version=component_config.cert_manager.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://charts.jetstack.io'},
        values={
            'crds': {
                'enabled': True,
            },
        },
        opts=k8s_opts,
    )

    # Create scoped down cloudflare token
    cloud_config = cloudflare.ApiToken(
        'cloudflare-token',
        name=f'microk8s-{p.get_stack()}-cert-manager',
        policies=[
            {
                'effect': 'allow',
                'permission_groups': [
                    # Zone Read
                    'c8fed203ed3043cba015a93ad1616f1f',
                    # DNS Write
                    '4755a26eedb94da69e1066d98aa820be',
                ],
                'resources': {'com.cloudflare.api.account.zone.*': '*'},
            },
        ],
        opts=p.ResourceOptions(provider=cloudflare_provider),
    )

    k8s_opts = p.ResourceOptions(provider=k8s_provider, depends_on=[chart])

    # Cloudflare DNS API Secret
    cloudflare_secret = k8s.core.v1.Secret(
        'cloudflare-api-token',
        metadata={'namespace': 'cert-manager'},
        type='Opaque',
        string_data={'api-token': cloud_config.value},
        opts=k8s_opts,
    )

    # Issuer
    return k8s.apiextensions.CustomResource(
        'letsencrypt-issuer',
        api_version='cert-manager.io/v1',
        kind='ClusterIssuer',
        metadata={'namespace': 'cert-manager', 'name': 'lets-encrypt'},
        spec={
            'acme': {
                'server': component_config.cert_manager.issuer_server,
                'email': component_config.cloudflare.email,
                'privateKeySecretRef': {'name': 'lets-encrypt-private-key'},
                'solvers': [
                    {
                        'dns01': {
                            'cloudflare': {
                                'apiTokenSecretRef': {
                                    'name': cloudflare_secret.metadata.name,
                                    'key': 'api-token',
                                },
                            },
                        },
                    },
                ],
            },
        },
        opts=k8s_opts,
    )

    # Test certificate
    # ruff: noqa: ERA001
    # k8s.apiextensions.CustomResource(
    #     'certificate',
    #     api_version='cert-manager.io/v1',
    #     kind='Certificate',
    #     metadata={'name': 'test-certificate'},
    #     spec={
    #         'secretName': 'test-certificate',
    #         'dnsNames': ['validate-cert.tobiash.net'],
    #         'issuerRef': {'name': 'lets-encrypt', 'kind': 'ClusterIssuer'},
    #     },
    #     opts=k8s_opts,
    # )
