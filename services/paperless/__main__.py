import pulumi as p
import pulumi_kubernetes as k8s

from paperless.config import ComponentConfig
from paperless.paperless import Paperless
from utils.k8s import get_k8s_provider

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

k8s_provider = get_k8s_provider()

namespace = k8s.core.v1.Namespace(
    'paperless-namespace',
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name='paperless',
    ),
    opts=p.ResourceOptions(
        provider=k8s_provider,
    ),
)

Paperless(
    component_config,
    namespace.metadata.name,
    k8s_provider,
)
