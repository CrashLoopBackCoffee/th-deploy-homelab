import ipaddress
import typing as t

import pydantic

import utils.model


class StrictBaseModel(pydantic.BaseModel):
    model_config = {'extra': 'forbid'}


class ProxmoxConfig(StrictBaseModel):
    username: str
    password: utils.model.OnePasswordRef
    api_endpoint: str = pydantic.Field(alias='api-endpoint')
    node_name: str = pydantic.Field(alias='node-name')
    insecure: bool = False


class MosquittoConfig(StrictBaseModel):
    version: str
    hostname: str
    passwords: list[str] = []


class MqttPrometheusInstanceConfig(StrictBaseModel):
    name: str
    topic_path: str = pydantic.Field(alias='topic-path')
    device_id_regex: str | None = pydantic.Field(alias='device-id-regex', default=None)
    metrics: list[dict[str, t.Any]] = []


class MqttPrometheusConfig(StrictBaseModel):
    version: str
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef
    instances: list[MqttPrometheusInstanceConfig] = []


class ZwaveAdapterConfig(StrictBaseModel):
    usb_id: str = pydantic.Field(alias='usb-id')
    serial_id: str = pydantic.Field(alias='serial-id')


class ZwaveControllerConfig(StrictBaseModel):
    address: ipaddress.IPv4Interface
    hostname: str
    cloud_image: str = pydantic.Field(
        alias='cloud-image',
        default='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
    )
    ssh_public_key: str = pydantic.Field(alias='ssh-public-key')
    vlan: int | None = None
    cores: int = 2
    memory_min: int = 1024
    memory_max: int = 2048
    disk_size: int = 20
    version: str
    zwave_adapter: ZwaveAdapterConfig = pydantic.Field(alias='zwave-adapter')


class ComponentConfig(StrictBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    proxmox: ProxmoxConfig

    cloudflare: utils.model.CloudflareConfig | None = None
    mosquitto: MosquittoConfig
    mqtt2prometheus: MqttPrometheusConfig
    zwave_controller: ZwaveControllerConfig


class StackConfig(StrictBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(StrictBaseModel):
    encryptionsalt: str | None
    config: StackConfig
