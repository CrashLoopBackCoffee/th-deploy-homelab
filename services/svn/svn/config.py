import utils.model


class SvnResourcesConfig(utils.model.LocalBaseModel):
    memory: str = '512Mi'
    cpu: str = '300m'


class SvnUser(utils.model.LocalBaseModel):
    username: str
    # Store a pre-generated htpasswd hash in 1Password
    password_hash: utils.model.OnePasswordRef


class SvnAuth(utils.model.LocalBaseModel):
    users: list[SvnUser] = []


class SvnConfig(utils.model.LocalBaseModel):
    # Full image tag including variant (e.g. "httpd-1.14.2")
    version: str
    resources: SvnResourcesConfig = SvnResourcesConfig()
    auth: SvnAuth


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    svn: SvnConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
