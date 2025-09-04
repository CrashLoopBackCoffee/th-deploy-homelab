import pulumi as p
import pulumi_kubernetes as k8s

from svn.config import ComponentConfig
from svn.svn import create_svn


def main() -> None:
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)

    assert component_config
    assert k8s_provider

    create_svn(component_config, k8s_provider)
