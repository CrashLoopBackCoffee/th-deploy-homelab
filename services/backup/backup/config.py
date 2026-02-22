import pydantic
import utils.model


class VolumeConfig(utils.model.LocalBaseModel):
    name: str
    nfs_server: str
    nfs_path: str
    nfs_mount_options: str = 'nfsvers=4.1,sec=sys'
    bucket: str

    @property
    def mount_path(self) -> str:
        return f'/mnt/{self.name}'


class S3Config(utils.model.LocalBaseModel):
    endpoint: utils.model.OnePasswordRef
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef


class ResticConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    restic: ResticConfig
    schedule: str = pydantic.Field(default='0 1 * * *')
    retention_daily: int = pydantic.Field(default=14)
    retention_weekly: int = pydantic.Field(default=8)
    retention_monthly: int = pydantic.Field(default=12)
    retention_yearly: int = pydantic.Field(default=5)
    restic_password: utils.model.OnePasswordRef
    s3: S3Config
    volumes: list[VolumeConfig]
    resources: utils.model.ResourcesConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None
    config: StackConfig
