import pathlib

import pulumi as p
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


class OnePasswordRef(LocalBaseModel):
    ref: str

    @property
    def value(self) -> p.Output[str]:
        # Lazy import to avoid importing pulumi_onepassword in the model
        from utils.onepassword import resolve_secret_ref  # noqa: PLC0415

        return resolve_secret_ref(self.ref)


class CloudflareConfig(LocalBaseModel):
    api_key: OnePasswordRef
    email: str
    zone: str


class ProxmoxConfig(LocalBaseModel):
    api_token: OnePasswordRef = pydantic.Field(alias='api-token')
    api_endpoint: str = pydantic.Field(alias='api-endpoint')
    node_name: str = pydantic.Field(alias='node-name')
    insecure: bool = False


class TargetConfig(LocalBaseModel):
    """
    Target config for remote commands"""

    host: str
    user: str
    root_dir: str
