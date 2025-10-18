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
postgres_provider, postgres_service, postgres_port = utils.postgres.create_postgres(
    component_config.postgres.version,
    namespace.metadata.name,
    k8s_provider,
)

assert component_config
assert k8s_provider

create_immich(
    component_config,
    namespace.metadata.name,
    k8s_provider,
    postgres_provider,
    postgres_service,
    postgres_port,
)
