import pulumi as p

from utils.k8s import get_k8s_provider

from tandoor.config import ComponentConfig
from tandoor.tandoor import create_tandoor


def main() -> None:
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    k8s_provider = get_k8s_provider()

    assert component_config
    assert k8s_provider

    create_tandoor(component_config, k8s_provider)
