"""A Python Pulumi program"""

import pulumi as p
import pulumi_kubernetes as k8s
import utils.postgres

from immich.config import ComponentConfig
from immich.immich import create_immich

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

stack = p.get_stack()
org = p.get_organization()
k8s_stack_ref = p.StackReference(f'{org}/kubernetes/{stack}')

k8s_provider = k8s.Provider('k8s', kubeconfig=k8s_stack_ref.get_output('kubeconfig'))

namespace = k8s.core.v1.Namespace(
    'immich-namespace',
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name='immich',
    ),
    opts=p.ResourceOptions(
        provider=k8s_provider,
    ),
)

# Create postgres database
postgres_db = utils.postgres.PostgresDatabase(
    'postgres',
    version='dummy',  # version is unused when using overriding the image name
    namespace_name=namespace.metadata.name,
    k8s_provider=k8s_provider,
    spec_overrides={
        # Use vectorchord-enabled PostgreSQL image for immich
        'imageName': f'ghcr.io/tensorchord/cloudnative-vectorchord:{component_config.postgres.vectorchord_version}',
        'postgresql': {
            'shared_preload_libraries': ['vchord.so'],
        },
        'bootstrap': {
            'initdb': {
                'postInitApplicationSQL': [
                    'CREATE EXTENSION vchord CASCADE;',
                    'CREATE EXTENSION earthdistance CASCADE;',
                ],
            },
        },
    },
)

assert component_config
assert k8s_provider

create_immich(
    component_config,
    namespace.metadata.name,
    k8s_provider,
    postgres_db,
)
