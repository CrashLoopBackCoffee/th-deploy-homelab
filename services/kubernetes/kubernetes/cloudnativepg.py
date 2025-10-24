import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_pulumiservice as pulumiservice
import yaml

from kubernetes.config import ComponentConfig


def create_cloudnative_pg(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """Create CloudNativePG operator for PostgreSQL cluster management."""
    namespace = k8s.core.v1.Namespace(
        'cnpg-system',
        metadata={'name': 'cnpg-system'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'cnpg-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Install CloudNativePG operator using Helm chart
    operator = k8s.helm.v4.Chart(
        'cloudnative-pg',
        chart='cloudnative-pg',
        version=component_config.cloudnative_pg.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://cloudnative-pg.github.io/charts'},
        values={
            'config': {
                'create': True,
                'secret': False,
            },
        },
        opts=k8s_opts,
    )

    # Install Barman Cloud Plugin (always)
    k8s.helm.v4.Chart(
        'plugin-barman-cloud',
        chart='plugin-barman-cloud',
        version=component_config.cloudnative_pg.barman_plugin_version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://cloudnative-pg.github.io/charts'},
        opts=k8s_opts,
    )

    # Create backup ObjectStore if backup is configured
    if component_config.cloudnative_pg.backup:
        # Export backup credentials to Pulumi ESC
        pulumiservice.Environment(
            'postgres-backup',
            organization=p.get_organization(),
            project=p.get_project(),
            name=f'postgres-backup-{p.get_stack()}',
            yaml=p.Output.from_input(
                {
                    'values': {
                        'destination-path': p.Output.concat(
                            's3://postgres',
                        ),
                        'endpoint-url': p.Output.concat(
                            'https://', component_config.cloudnative_pg.backup.endpoint.value
                        ),
                        'access-key-id': {
                            'fn::secret': component_config.cloudnative_pg.backup.access_key_id.value
                        },
                        'secret-access-key': {
                            'fn::secret': component_config.cloudnative_pg.backup.secret_access_key.value
                        },
                        'pulumiConfig': {
                            'postgres-backup': {
                                'destination-path': '${destination-path}',
                                'endpoint-url': '${endpoint-url}',
                                'access-key-id': '${access-key-id}',
                                'secret-access-key': '${secret-access-key}',
                            },
                        },
                    },
                },
            ).apply(lambda c: yaml.safe_dump(c)),  # pyright: ignore[reportArgumentType]
        )

    return operator
