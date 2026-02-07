import pulumi as p

from utils.k8s import get_k8s_provider

from strava_sensor.config import ComponentConfig
from strava_sensor.strava_sensor import create_strava_sensor


def main() -> None:
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    create_strava_sensor(component_config, get_k8s_provider())
