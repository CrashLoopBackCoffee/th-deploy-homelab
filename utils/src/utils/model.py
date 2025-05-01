import pydantic


def _to_kebap_case(name: str) -> str:
    return name.replace('_', '-')


class LocalBaseModel(pydantic.BaseModel):
    model_config = {
        'extra': 'forbid',
        'alias_generator': _to_kebap_case,
        # Allow instanciation also with original names
        'populate_by_name': True,
    }


class OnePasswordRef(LocalBaseModel):
    ref: str

    @property
    def value(self):
        # Lazy import to avoid importing pulumi_onepassword in the model
        from utils.onepassword import resolve_secret_ref

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
