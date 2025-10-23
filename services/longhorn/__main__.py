"""Longhorn distributed block storage service for Kubernetes"""

import pulumi as p
import pulumi_kubernetes as k8s

from longhorn.config import ComponentConfig
from longhorn.longhorn import Longhorn

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

stack = p.get_stack()
org = p.get_organization()
k8s_stack_ref = p.StackReference(f'{org}/kubernetes/{stack}')

k8s_provider = k8s.Provider('k8s', kubeconfig=k8s_stack_ref.get_output('kubeconfig'))

# Deploy Longhorn
longhorn = Longhorn(
    'longhorn',
    component_config=component_config,
    k8s_provider=k8s_provider,
)

# Export outputs
if component_config.longhorn.hostname:
    p.export('url', longhorn.url)
    p.export('lb_ip', longhorn.lb_ip)
