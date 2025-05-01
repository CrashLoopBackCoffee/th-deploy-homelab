import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_postgresql as postgresql
import pulumi_random

import deploy_base
import deploy_base.port_forward


def create_postgres(
    version: str,
    namespace_name: p.Input[str],
    k8s_provider: k8s.Provider,
    local_port: int = 15432,
) -> tuple[postgresql.Provider, p.Output[str], int]:
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    root_password = pulumi_random.RandomPassword(
        'postgres-password',
        length=24,
    )

    chart = k8s.helm.v3.Release(
        'postgres',
        chart='oci://registry-1.docker.io/bitnamicharts/postgresql',
        version=version,
        namespace=namespace_name,
        values={
            'auth': {
                'postgresPassword': root_password.result,
            },
            'metrics': {'enabled': True},
        },
        opts=k8s_opts,
    )

    postgres_service = chart.resource_names.apply(
        lambda names: [name for name in names['Service/v1'] if name.endswith('postgresql')][0]  # type: ignore
    ).apply(lambda name: name.split('/')[-1])

    postgres_port = deploy_base.port_forward.ensure_port_forward(
        local_port=local_port,
        namespace=namespace_name,
        resource_type=deploy_base.port_forward.ResourceType.SERVICE,
        resource_name=postgres_service,
        target_port='tcp-postgresql',
        k8s_provider=k8s_provider,
    )

    return (
        postgresql.Provider(
            'postgres',
            host='localhost',
            port=postgres_port,
            sslmode='disable',
            password=root_password.result,
        ),
        postgres_service,
        5432,
    )
