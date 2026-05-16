import pydantic
import utils.model


class StravaSensorStorageConfig(utils.model.LocalBaseModel):
    state_size: str = pydantic.Field(default='256Mi', alias='state-size')


class StravaSensorConfig(utils.model.LocalBaseModel):
    version: str
    webhook_url: str = pydantic.Field(alias='webhook-url')
    webhook_registration_delay: int | None = pydantic.Field(
        default=None, alias='webhook-registration-delay'
    )
    resources: utils.model.ResourcesConfig
    storage: StravaSensorStorageConfig = StravaSensorStorageConfig()


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
