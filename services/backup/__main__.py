import pulumi as p
import pulumi_kubernetes as k8s

from backup.backup import Backup
from backup.config import ComponentConfig
from utils.k8s import get_k8s_provider

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

k8s_provider = get_k8s_provider()

namespace = k8s.core.v1.Namespace(
    'backup',
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name='backup',
        labels={'goldilocks.fairwinds.com/enabled': 'true'},
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
