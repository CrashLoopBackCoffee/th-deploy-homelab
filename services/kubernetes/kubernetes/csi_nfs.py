import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_csi_nfs(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    k8s.helm.v4.Chart(
        'csi-driver-nfs',
        chart='csi-driver-nfs',
        namespace='kube-system',
        version=component_config.csi_nfs_driver.version,
        repository_opts={
            'repo': 'https://raw.githubusercontent.com/kubernetes-csi/csi-driver-nfs/master/charts'
        },
        values={
            'kubeletDir': '/var/snap/microk8s/common/var/lib/kubelet',
            'feature': {
                'enableInlineVolume': True,
            },
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )
