import pulumi as p
import pulumi_kubernetes as k8s

from backup.backup import Backup
from backup.config import ComponentConfig

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)

namespace = k8s.core.v1.Namespace(
    'backup',
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name='backup',
    ),
    opts=p.ResourceOptions(
        provider=k8s_provider,
    ),
)

Backup(
    component_config,
    namespace.metadata.name,
    k8s_provider,
)
