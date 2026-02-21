import ipaddress
import typing as t

import pydantic
import utils.model


class ProxmoxConfig(utils.model.LocalBaseModel):
    username: str
    password: utils.model.OnePasswordRef
    api_endpoint: str
    node_name: str
    insecure: bool = False


class MosquittoConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    passwords: list[str] = []


class MqttPrometheusInstanceConfig(utils.model.LocalBaseModel):
    name: str
    topic_path: str
    device_id_regex: str | None = None
    metrics: list[dict[str, t.Any]] = []


class MqttPrometheusConfig(utils.model.LocalBaseModel):
    version: str
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef
    instances: list[MqttPrometheusInstanceConfig] = []


class ZwaveAdapterConfig(utils.model.LocalBaseModel):
    usb_id: str
    serial_id: str


class ZwaveControllerConfig(utils.model.LocalBaseModel):
    address: ipaddress.IPv4Interface
    hostname: str
    cloud_image: str = pydantic.Field(
        default='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
    )
    ssh_public_key: str
    vlan: int | None = None
    cores: int = 2
    memory_min: int = 1024
    memory_max: int = 2048
    disk_size: int = 20
    version: str
    alloy_version: str
    zwave_adapter: ZwaveAdapterConfig


class ComponentConfig(utils.model.LocalBaseModel):
    proxmox: ProxmoxConfig

    cloudflare: utils.model.CloudflareConfig | None = None
    mosquitto: MosquittoConfig
    mqtt2prometheus: MqttPrometheusConfig
    zwave_controller: ZwaveControllerConfig


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
