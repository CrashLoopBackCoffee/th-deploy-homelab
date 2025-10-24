import pulumi as p
import pulumi_proxmoxve as proxmoxve

from utils.k8s import get_k8s_provider

from iot.config import ComponentConfig
from iot.mosquitto import Mosquitto
from iot.mqtt2prometheus import Mqtt2Prometheus
from iot.zwave_controller import ZwaveeController


def main():
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    k8s_provider = get_k8s_provider()
    proxmox_provider = proxmoxve.Provider(
        'proxmox',
        endpoint=component_config.proxmox.api_endpoint,
        username=component_config.proxmox.username,
        password=component_config.proxmox.password.value,
        insecure=component_config.proxmox.insecure,
        ssh={
            'username': 'root',
            'agent': True,
        },
    )

    Mosquitto('mosquitto', component_config, k8s_provider)

    Mqtt2Prometheus('mqtt2prometheus', component_config, k8s_provider)

    ZwaveeController(
        'zwave-controller',
        component_config,
        proxmox_provider,
    )
