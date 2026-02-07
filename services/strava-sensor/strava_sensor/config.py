import pydantic
import utils.model


class MqttConfig(utils.model.LocalBaseModel):
    broker_url: str = pydantic.Field(alias='broker-url')
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef


class GarminConfig(utils.model.LocalBaseModel):
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef


class StravaConfig(utils.model.LocalBaseModel):
    refresh_token: utils.model.OnePasswordRef = pydantic.Field(alias='refresh-token')
    client_id: utils.model.OnePasswordRef = pydantic.Field(alias='client-id')
    client_secret: utils.model.OnePasswordRef = pydantic.Field(alias='client-secret')


class StravaSensorResourcesConfig(utils.model.LocalBaseModel):
    memory: str = '256Mi'
    cpu: str = '100m'


class StravaSensorStorageConfig(utils.model.LocalBaseModel):
    state_size: str = pydantic.Field(default='256Mi', alias='state-size')


class StravaSensorConfig(utils.model.LocalBaseModel):
    version: str
    webhook_url: str = pydantic.Field(alias='webhook-url')
    webhook_registration_delay: int | None = pydantic.Field(
        default=None, alias='webhook-registration-delay'
    )
    resources: StravaSensorResourcesConfig = StravaSensorResourcesConfig()
    storage: StravaSensorStorageConfig = StravaSensorStorageConfig()
    garmin: GarminConfig | None = None
    strava: StravaConfig
    mqtt: MqttConfig


class ComponentConfig(utils.model.LocalBaseModel):
    strava_sensor: StravaSensorConfig = pydantic.Field(alias='strava-sensor')


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
