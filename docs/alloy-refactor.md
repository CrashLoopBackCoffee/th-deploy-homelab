# Alloy Refactoring PRD

This document outlines the plan to refactor the `alloy` component in the monitoring service. The primary goal is to establish a new, centralized Alloy instance for the `prod` environment while maintaining the existing `alloy_legacy` instance for local data collection on Synology.

The new `alloy` service will handle the main OpenTelemetry (OTel) pipeline, while the `alloy_legacy` service will be reconfigured to forward its data to the new service.

A feature branch should be created before implementation begins, and each major step should be committed separately to maintain a clean history.

## Phase 1: Preparation and Cleanup

This phase focuses on renaming existing resources to avoid conflicts and prepare for the new service.

### 1.1. Create a feature branch

Create a new feature branch from the `main` branch.

```bash
git checkout -b feature/alloy-refactor
```

### 1.2. Rename `alloy` assets to `alloy_legacy`

To differentiate the configurations, we will rename the asset directory.

*   **Action:** Rename the directory `services/monitoring/assets/alloy` to `services/monitoring/assets/alloy_legacy`.
    ```bash
    mv services/monitoring/assets/alloy services/monitoring/assets/alloy_legacy
    ```

### 1.3. Update `alloy_legacy.py` to use the new asset path

The Pulumi code for the legacy component needs to point to the new asset path.

*   **File to edit:** `services/monitoring/monitoring/alloy_legacy.py`
*   **Change:** Update the `alloy_path` variable to reflect the new directory name.
    *   **From:** `alloy_path = get_assets_path() / 'alloy'`
    *   **To:** `alloy_path = get_assets_path() / 'alloy_legacy'`

### 1.4. Update configuration schema for dual alloy services

The configuration model needs to support both the new `alloy` service and the existing `alloy_legacy` service.

*   **File to edit:** `services/monitoring/monitoring/config.py`
*   **Changes:**
    *   **Rename:** `AlloyConfig` to `AlloyLegacyConfig`
    *   **Add:** New `AlloyConfig` class for the Kubernetes-based service (without username/token fields)
    *   **Update:** `ComponentConfig` to include both `alloy: AlloyConfig | None = None` and keep existing `alloy: AlloyConfig | None = None` as `alloy_legacy: AlloyLegacyConfig | None = None`

### 1.5. Rename the `alloy_legacy` service hostname

The hostname will be updated to reflect its "legacy" status.

*   **File to edit:** `services/monitoring/monitoring/alloy_legacy.py`
*   **Change:** Update the Cloudflare CNAME record to `alloy-legacy`.
    *   **From:** `dns_record = utils.cloudflare.create_cloudflare_cname('alloy', ...)`
    *   **To:** `dns_record = utils.cloudflare.create_cloudflare_cname('alloy-legacy', ...)`
*   **File to edit:** `services/monitoring/Pulumi.dev.yaml`
*   **Change:** The hostname is not explicitly in the config, but the DNS record change will cause the deployed URL to change. We need to run `pulumi up` on the `dev` stack to apply this change.

## Phase 2: Implement the New `alloy` Service

This phase involves creating the new Pulumi component for the main `alloy` service.

### 2.1. Create new asset directory and configuration

Create the asset directory for the new Kubernetes-based Alloy service.

*   **Action:** Create the directory `services/monitoring/assets/alloy`
    ```bash
    mkdir -p services/monitoring/assets/alloy
    ```
*   **Action:** Copy initial configuration files from `alloy_legacy` as a starting point, then modify for Kubernetes deployment (remove Docker socket mounts, adjust for TLS, etc.)

### 2.2. Create `alloy.py` component

Create a new file `services/monitoring/monitoring/alloy.py` for the new service. This will follow Kubernetes deployment patterns similar to `grafana.py`, not the Docker-on-remote-host pattern of `alloy_legacy.py`.

*   **Key elements to include:**
    *   A new `create_alloy` function following the same pattern as `create_grafana` in `grafana.py`
    *   **Kubernetes Deployment:** Use `k8s.apps.v1.Deployment` with the Alloy container image
    *   **Namespace:** Create dedicated `alloy` namespace following the same pattern as Grafana
    *   **ConfigMap:** Mount Alloy configuration files from `services/monitoring/assets/alloy/`
    *   **PersistentVolumeClaim:** For Alloy data storage
    *   Use `alloy.tobiash.net` as the hostname
    *   **Expose via MetalLB LoadBalancer:** Create a `k8s.core.v1.Service` of `type: 'LoadBalancer'` to expose the `alloy` service. This will expose both the management port (12345) and the OTel receiver ports (4317, 4318)
    *   **TLS Certificate with `cert-manager`:** Create a `k8s.apiextensions.CustomResource` of `kind: 'Certificate'` with `api_version: 'cert-manager.io/v1'` to provision a TLS certificate for `alloy.tobiash.net`
    *   **Local DNS:** Create a local DNS record using the `utils.opnsense.unbound.host_override.HostOverride` component to point `alloy.tobiash.net` to the LoadBalancer IP

### 2.3. Update `Pulumi.prod.yaml`

Add the configuration for the new `alloy` service to the `prod` stack.

*   **File to edit:** `services/monitoring/Pulumi.prod.yaml`
*   **Action:** Add a new `alloy` section with the required version and hostname configuration, following the same pattern as `grafana`:
    ```yaml
    alloy:
      # renovate: datasource=github-releases packageName=grafana/alloy versioning=semver
      version: v1.10.1
      hostname: alloy.tobiash.net
    ```

### 2.4. Update `main.py` to deploy the new service

The main entrypoint for the monitoring service needs to be updated to call the new `create_alloy` function.

*   **File to edit:** `services/monitoring/monitoring/main.py`
*   **Changes:**
    *   **Add import:** `from monitoring.alloy import create_alloy`
    *   **Add function call:** `create_alloy(component_config, k8s_provider)` in the `main()` function

## Phase 3: Migration and Finalization

This phase focuses on reconfiguring the `alloy_legacy` service to forward data to the new `alloy` service.

### 3.1. Update `alloy_legacy` configuration

Modify the Alloy configuration files in `services/monitoring/assets/alloy_legacy/` to:
*   Remove any configuration that is now handled by the new `alloy` service.
*   Keep only the local data gathering configuration (e.g., Synology logs).
*   Add a `forward_to` block to send all collected data to the new `alloy` service's OTel receiver endpoint (`alloy.tobiash.net:4317` or similar).

### 3.2. Deploy all changes with verification

Run deployments with proper verification steps, following project standards.

*   **CRITICAL: Run code quality checks first:**
    ```bash
    uv run ./scripts/run-all-checks.sh
    ```

*   **Deploy `prod` stack (new alloy service):**
    ```bash
    (cd services/monitoring && pulumi preview -s prod --diff --non-interactive)
    (cd services/monitoring && pulumi up -s prod --non-interactive --skip-preview)
    ```

*   **Deploy `dev` stack (updated alloy_legacy service):**
    ```bash
    (cd services/monitoring && pulumi preview -s dev --diff --non-interactive)
    (cd services/monitoring && pulumi up -s dev --non-interactive --skip-preview)
    ```

### 3.3. Verification

After deployment, verify that:
*   The new `alloy` service is running and accessible at `https://alloy.tobiash.net`.
*   The `alloy_legacy` service is running and forwarding data to the new service.
*   Metrics and logs are flowing through the new pipeline into Grafana/Loki/Mimir correctly.

## Implementation Notes

### Critical Requirements Addressed:

1. **Configuration Schema:** Updated to support both `alloy` (Kubernetes) and `alloy_legacy` (Docker) services
2. **Asset Directory:** New `/assets/alloy/` directory for Kubernetes-specific configs
3. **Kubernetes Patterns:** Following established patterns from `grafana.py` instead of Docker deployment
4. **Project Standards:** Added proper renovate comments, code quality checks, and pulumi preview steps
5. **Import Structure:** Explicit import and function call additions to `main.py`

### Key Architectural Decisions:

- **New `alloy`**: Kubernetes-native deployment in `prod` stack using MetalLB LoadBalancer and cert-manager
- **Legacy `alloy_legacy`**: Remains Docker-based on Synology, reconfigured to forward to new service
- **Configuration separation**: Distinct config classes and asset directories for each deployment model
- **TLS termination**: Handled by cert-manager for the new service, direct in container for legacy

This comprehensive plan addresses all the critical gaps identified in the original design and provides a production-ready implementation path.
