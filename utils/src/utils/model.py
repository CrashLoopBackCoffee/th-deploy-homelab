import pathlib

import pulumi_kubernetes as k8s
import pydantic


def get_pulumi_project(model_dir: str):
    search_dir = pathlib.Path(model_dir).parent

    while not (search_dir / 'Pulumi.yaml').exists():
        if not search_dir.parents:
            raise ValueError('Could not find repo root')

        search_dir = search_dir.parent
    return search_dir.name


def _to_kebap_case(name: str) -> str:
    return name.replace('_', '-')


class LocalBaseModel(pydantic.BaseModel):
    model_config = {
        'extra': 'forbid',
        'alias_generator': _to_kebap_case,
        # Allow instanciation also with original names
        'populate_by_name': True,
    }


class PulumiSecret(LocalBaseModel):
    secure: pydantic.SecretStr

    def __str__(self):
        return str(self.secure)


class TargetConfig(LocalBaseModel):
    """
    Target config for remote commands"""

    host: str
    user: str
    root_dir: str


class ResourcesConfig(LocalBaseModel):
    cpu: str
    memory: str

    def to_resource_requirements(self) -> k8s.core.v1.ResourceRequirementsArgsDict:
        return {
            'requests': {'cpu': self.cpu, 'memory': self.memory},
            'limits': {'memory': self.memory},
        }


class PostgresBackupConfig(LocalBaseModel):
    cron_schedule: str = '0 0 0 * * *'
