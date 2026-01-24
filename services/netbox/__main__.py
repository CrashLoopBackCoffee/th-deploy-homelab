import pulumi as p
import pulumi_kubernetes as k8s

from netbox.config import ComponentConfig
from netbox.netbox import Netbox
from utils.k8s import get_k8s_provider

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

k8s_provider = get_k8s_provider()

namespace = k8s.core.v1.Namespace(
    'netbox-namespace',
    metadata={'name': 'netbox'},
    opts=p.ResourceOptions(
        provider=k8s_provider,
    ),
)

Netbox(
    component_config,
    namespace.metadata.name,
    k8s_provider,
)
