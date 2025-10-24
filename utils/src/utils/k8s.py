import pulumi as p
import pulumi_kubernetes as k8s


def get_k8s_provider() -> k8s.Provider:
    return k8s.Provider('k8s', kubeconfig=p.Config().require_secret('kubeconfig'))
