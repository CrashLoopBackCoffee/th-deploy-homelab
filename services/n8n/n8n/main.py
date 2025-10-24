import pulumi as p

from utils.k8s import get_k8s_provider

from n8n.config import ComponentConfig
from n8n.n8n import create_n8n


def main() -> None:
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    create_n8n(component_config, get_k8s_provider())
