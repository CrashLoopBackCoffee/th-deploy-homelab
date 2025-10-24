import pydantic
import utils.model


class EntraIdConfig(utils.model.LocalBaseModel):
    tenant_id: str = 'ac1df362-04cf-4e6e-839b-031c16ada473'
    client_id: str
    client_secret: str | utils.model.PulumiSecret


class GoogleConfig(utils.model.LocalBaseModel):
    client_id: str
    client_secret: str | utils.model.PulumiSecret


class RedisConfig(utils.model.LocalBaseModel):
    version: str


class TikaConfig(utils.model.LocalBaseModel):
    version: str


class GotenbergConfig(utils.model.LocalBaseModel):
    version: str


class PostgresConfig(utils.model.LocalBaseModel):
    version: str


class MailConfig(utils.model.LocalBaseModel):
    client_id: str
    client_secret: str | utils.model.PulumiSecret


class PaperlessConfig(utils.model.LocalBaseModel):
    version: str

    consume_server: str = pydantic.Field(alias='consume-server')
    consume_share: str = pydantic.Field(alias='consume-share')
    consume_mount_options: str = pydantic.Field(
        alias='consume-mount-options', default='nfsvers=4.1,sec=sys'
    )


class RcloneGoogleDriveConfig(utils.model.LocalBaseModel):
    client_id: utils.model.OnePasswordRef
    client_secret: utils.model.OnePasswordRef
    access_token: utils.model.OnePasswordRef
    refresh_token: utils.model.OnePasswordRef
    token_expiry: str = pydantic.Field(alias='token-expiry')
    root_folder_id: str = pydantic.Field(alias='root-folder-id')


class BackupConfig(utils.model.LocalBaseModel):
    restic_rclone_version: str = pydantic.Field(alias='restic-rclone-version')
    kubectl_version: str = pydantic.Field(alias='kubectl-version')
    restic_password: utils.model.OnePasswordRef = pydantic.Field(alias='restic-password')
    repository_path: str = pydantic.Field(alias='repository-path', default='paperless')
    schedule: str = pydantic.Field(default='0 2 * * *')
    retention_daily: int = pydantic.Field(alias='retention-daily', default=7)
    retention_weekly: int = pydantic.Field(alias='retention-weekly', default=4)
    retention_monthly: int = pydantic.Field(alias='retention-monthly', default=6)
    google_drive: RcloneGoogleDriveConfig = pydantic.Field(alias='google-drive')
    # Optional secondary S3-compatible repository (IDrive E2) for redundancy.
    # When enabled, a second restic repository will be configured pointing at the
    # provided bucket. Backups will be pushed to both remote locations.
    idrive_enabled: bool = False
    idrive_endpoint: utils.model.OnePasswordRef | None = None
    idrive_bucket: str | None = None
    idrive_access_key_id: utils.model.OnePasswordRef | None = None
    idrive_secret_access_key: utils.model.OnePasswordRef | None = None


class ComponentConfig(utils.model.LocalBaseModel):
    cloudflare: utils.model.CloudflareConfig
    paperless: PaperlessConfig
    backup: BackupConfig
    redis: RedisConfig
    entraid: EntraIdConfig
    google: GoogleConfig
    mail: MailConfig
    postgres: PostgresConfig
    tika: TikaConfig
    gotenberg: GotenbergConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    environment: list[str] | None
    config: StackConfig
