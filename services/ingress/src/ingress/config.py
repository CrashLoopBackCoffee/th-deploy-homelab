import pathlib

import deploy_base.model

REPO_PREFIX = 'deploy-'


def get_pulumi_project():
    repo_dir = pathlib.Path().resolve()

    while not repo_dir.name.startswith(REPO_PREFIX):
        if not repo_dir.parents:
            raise ValueError('Could not find repo root')

        repo_dir = repo_dir.parent
    return repo_dir.name[len(REPO_PREFIX) :]


class CloudflareIngressConfig(deploy_base.model.LocalBaseModel):
    service: str
    hostname: str
    set_origin_server_name: bool = False


class CloudflaredConfig(deploy_base.model.LocalBaseModel):
    version: str
    ingress: list[CloudflareIngressConfig] = []


class ComponentConfig(deploy_base.model.LocalBaseModel):
    cloudflare: deploy_base.model.CloudflareConfig
    cloudflared: CloudflaredConfig


class StackConfig(deploy_base.model.LocalBaseModel):
    model_config = {'alias_generator': lambda field_name: f'{get_pulumi_project()}:{field_name}'}
    config: ComponentConfig


class PulumiConfigRoot(deploy_base.model.LocalBaseModel):
    config: StackConfig
