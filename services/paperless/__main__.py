import pulumi as p
import pulumi_kubernetes as k8s
import utils.postgres

from paperless.config import ComponentConfig
from paperless.paperless import Paperless
from utils.postgres import PostgresBackend

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)

namespace = k8s.core.v1.Namespace(
    'paperless-namespace',
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name='paperless',
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
    backend=PostgresBackend.BITNAMI,
)

Paperless(
    component_config,
    namespace.metadata.name,
    k8s_provider,
    postgres_provider,
    postgres_service,
    postgres_port,
)
