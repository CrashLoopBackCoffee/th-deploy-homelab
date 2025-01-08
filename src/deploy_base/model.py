import pydantic


class StrictBaseModel(pydantic.BaseModel):
    model_config = {'extra': 'forbid'}


class OnePasswordRef(StrictBaseModel):
    ref: str

    @property
    def value(self):
        # Lazy import to avoid importing pulumi_onepassword in the model
        from deploy_base.onepassword import resolve_secret_ref

        return resolve_secret_ref(self.ref)


class CloudflareConfig(StrictBaseModel):
    api_key: OnePasswordRef = pydantic.Field(alias='api-key')
    email: str
    zone: str
