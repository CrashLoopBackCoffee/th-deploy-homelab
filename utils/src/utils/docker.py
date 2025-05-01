import pulumi_docker as docker

from utils.model import TargetConfig


def get_provider(config: TargetConfig) -> docker.Provider:
    return docker.Provider(
        config.host,
        host=f'ssh://{config.host}',
    )
