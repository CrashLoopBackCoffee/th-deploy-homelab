import pulumi as p

from utils.k8s import get_k8s_provider

from ollama.config import ComponentConfig
from ollama.ollama import create_ollama


def main():
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    k8s_provider = get_k8s_provider()

    assert component_config
    assert k8s_provider

    create_ollama(component_config, k8s_provider)
