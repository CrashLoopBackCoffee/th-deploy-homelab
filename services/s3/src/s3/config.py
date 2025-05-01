import pathlib

import pydantic

REPO_PREFIX = 'deploy-'


class StrictBaseModel(pydantic.BaseModel):
    model_config = {'extra': 'forbid'}


class PulumiSecret(StrictBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class TargetConfig(StrictBaseModel):
    host: str
    user: str
    root_dir: str


def get_pulumi_project():
    repo_dir = pathlib.Path().resolve()

    while not repo_dir.name.startswith(REPO_PREFIX):
        if not repo_dir.parents:
            raise ValueError('Could not find repo root')

        repo_dir = repo_dir.parent
    return repo_dir.name[len(REPO_PREFIX) :]


class CloudflareConfig(StrictBaseModel):
    api_key: PulumiSecret | str = pydantic.Field(alias='api-key')
    email: str
    zone: str


class MinioConfig(StrictBaseModel):
    version: str


class ComponentConfig(StrictBaseModel):
    target: TargetConfig
    cloudflare: CloudflareConfig
    minio: MinioConfig


class StackConfig(StrictBaseModel):
    model_config = {'alias_generator': lambda field_name: f'{get_pulumi_project()}:{field_name}'}
    config: ComponentConfig


class PulumiConfigRoot(StrictBaseModel):
    config: StackConfig
