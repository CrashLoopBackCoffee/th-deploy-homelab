import pulumi as p
import pulumi_kubernetes as k8s

from backup.config import ComponentConfig
from backup.cronjob import create_backup_cronjob


class Backup(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace_name: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('backup:backup', 'backup')

        self.component_config = component_config
        self.namespace_name = namespace_name
        self.k8s_provider = k8s_provider

        # Create namespaced provider for backup resources
        namespaced_provider = k8s.Provider(
            'backup-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace_name,
        )

        # Resource options for all backup resources
        k8s_opts = p.ResourceOptions(
            provider=namespaced_provider,
            parent=self,
        )

        # Create backup CronJob
        self.cronjob = create_backup_cronjob(component_config, k8s_opts)

        # Export useful outputs
        p.export('backup_cronjob_name', self.cronjob.metadata.name)
        p.export('backup_schedule', component_config.schedule)
