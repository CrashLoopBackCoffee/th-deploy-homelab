import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig
from monitoring.mimir_buckets import MimirBuckets


class Mimir(p.ComponentResource):
    def __init__(
        self,
        name: str,
        component_config: ComponentConfig,
        cloudflare_provider: cloudflare.Provider,
        mimir_buckets: MimirBuckets,
        k8s_provider: k8s.Provider,
    ):
        super().__init__(f'lab:mimir:{name}', name)

        self.register_outputs({})
