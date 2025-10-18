"""A Python Pulumi program"""

import pulumi as p
import pulumi_kubernetes as k8s

from immich.config import ComponentConfig
from immich.immich import create_immich

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

stack = p.get_stack()
org = p.get_organization()
k8s_stack_ref = p.StackReference(f'{org}/kubernetes/{stack}')

k8s_provider = k8s.Provider('k8s', kubeconfig=k8s_stack_ref.get_output('kubeconfig'))

assert component_config
assert k8s_provider

create_immich(component_config, k8s_provider)
