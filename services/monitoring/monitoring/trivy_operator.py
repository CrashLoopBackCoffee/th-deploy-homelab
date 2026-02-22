import pulumi as p
import pulumi_kubernetes as k8s

from monitoring.config import ComponentConfig


def create_trivy_operator(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """
    Deploy Trivy Operator to scan for security vulnerabilities in the cluster.
    """
    k8s_opts = p.ResourceOptions(provider=k8s_provider)

    namespace = k8s.core.v1.Namespace(
        'trivy-system',
        metadata={'name': 'trivy-system'},
        opts=k8s_opts,
    )

    k8s.helm.v4.Chart(
        'trivy-operator',
        chart='trivy-operator',
        version=component_config.trivy_operator.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://aquasecurity.github.io/helm-charts/'},
        values={
            'podAnnotations': {
                # Enable Prometheus scraping on the default metrics port (8080)
                'prometheus.io/scrape': 'true',
                'prometheus.io/port': '8080',
            },
            'operator': {
                # Single-node homelab: run scans one at a time to avoid overloading the node
                'scanJobsConcurrentLimit': 1,
                # Auto-clean completed scan jobs after 60 s so they don't pile up
                'scanJobTTL': '60s',
                # SBOM generation doubles the number of scan jobs; disable it
                # (ClusterVulnerabilityReports are not needed in a homelab)
                'sbomGenerationEnabled': False,
                # Re-scan every workload daily: when a VulnerabilityReport exceeds this TTL
                # the operator treats it as stale and re-queues a scan job automatically.
                # This is trivy-operator's "nightly scan" mechanism (no built-in cron).
                'scannerReportTTL': '24h',
                # Expose per-CVE-ID metrics (trivy_vulnerability_id gauge).
                # Increases metric cardinality but enables CVE-level alerting/dashboards.
                'metricsVulnIdEnabled': True,
            },
        },
        opts=p.ResourceOptions(provider=k8s_provider, depends_on=[namespace]),
    )
