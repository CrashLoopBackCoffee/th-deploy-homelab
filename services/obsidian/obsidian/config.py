import utils.model


class CloudflaredConfig(utils.model.LocalBaseModel):
    version: str


class CouchDBConfig(utils.model.LocalBaseModel):
    username: str
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    target: utils.model.TargetConfig
    cloudflare: utils.model.CloudflareConfig
    couchdb: CouchDBConfig
    cloudflared: CloudflaredConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
