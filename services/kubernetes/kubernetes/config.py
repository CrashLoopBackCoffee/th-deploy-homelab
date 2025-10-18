import ipaddress

import pydantic
import utils.model


class ProxmoxConfig(utils.model.LocalBaseModel):
    api_token: utils.model.OnePasswordRef
    api_endpoint: str
    node_name: str
    insecure: bool = False


class DiskConfig(utils.model.LocalBaseModel):
    size: int


class MetallbConfig(utils.model.LocalBaseModel):
    version: str
    start: ipaddress.IPv4Address
    end: ipaddress.IPv4Address


class NfsCsiDriverConfig(utils.model.LocalBaseModel):
    version: str


class TraeficConfig(utils.model.LocalBaseModel):
    version: str


class MicroK8sInstanceConfig(utils.model.LocalBaseModel):
    name: str
    cores: int
    memory_min: int
    memory_max: int
    disks: list[DiskConfig]
    address: ipaddress.IPv4Interface


class MicroK8sConfig(utils.model.LocalBaseModel):
    vlan: int | None = None
    cloud_image: str = pydantic.Field(
        default='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img',
    )
    ssh_public_key: str
    master_nodes: list[MicroK8sInstanceConfig]
    metallb: MetallbConfig
    version: str


class CertManagerConfig(utils.model.LocalBaseModel):
    version: str
    use_staging: bool = False

    @property
    def issuer_server(self):
        return (
            'https://acme-staging-v02.api.letsencrypt.org/directory'
            if self.use_staging
            else 'https://acme-v02.api.letsencrypt.org/directory'
        )


class CloudNativePgConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    cert_manager: CertManagerConfig
    cloudflare: utils.model.CloudflareConfig
    cloudnative_pg: CloudNativePgConfig
    proxmox: ProxmoxConfig
    microk8s: MicroK8sConfig
    csi_nfs_driver: NfsCsiDriverConfig
    traefik: TraeficConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
