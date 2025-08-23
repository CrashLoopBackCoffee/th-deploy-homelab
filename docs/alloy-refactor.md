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

### 1.4. Rename the `alloy_legacy` service hostname

The hostname will be updated to reflect its "legacy" status.

*   **File to edit:** `services/monitoring/monitoring/alloy_legacy.py`
*   **Change:** Update the Cloudflare CNAME record to `alloy-legacy`.
    *   **From:** `dns_record = utils.cloudflare.create_cloudflare_cname('alloy', ...)`
    *   **To:** `dns_record = utils.cloudflare.create_cloudflare_cname('alloy-legacy', ...)`
    *   **From:** `utils.cloudflare.delete_cloudflare_cname('alloy')`
    *   **To:** `utils.cloudflare.delete_cloudflare_cname('alloy-legacy')`
*   **File to edit:** `services/monitoring/Pulumi.dev.yaml`
*   **Change:** The hostname is not explicitly in the config, but the DNS record change will cause the deployed URL to change. We need to run `pulumi up` on the `dev` stack to apply this change.

## Phase 2: Implement the New `alloy` Service

This phase involves creating the new Pulumi component for the main `alloy` service.

### 2.1. Create `alloy.py` component

Create a new file `services/monitoring/monitoring/alloy.py` for the new service. This will be a simplified version of `alloy_legacy.py`, tailored for the `prod` environment.

*   **Key elements to include:**
    *   A new `create_alloy` function.
    *   Docker container deployment using the version from `Pulumi.prod.yaml`.
    *   Configuration for the main OTel pipeline.
    *   Exclude local-only features like Docker log gathering (`/var/run/docker.sock`).
    *   Use `alloy.tobiash.net` as the hostname.
    *   **Expose via MetalLB LoadBalancer:** Create a `k8s.core.v1.Service` of `type: 'LoadBalancer'` to expose the `alloy` service. This will expose both the management port (e.g., 9091) and the OTel receiver ports (e.g., 4317, 4318).
    *   **TLS Certificate with `cert-manager`:** Create a `k8s.apiextensions.CustomResource` of `kind: 'Certificate'` with `api_version: 'cert-manager.io/v1'` to provision a TLS certificate for `alloy.tobiash.net`. The `secretName` from this resource will be used to mount the TLS certificate into the `alloy` pod.
    *   **Configure `alloy` for TLS:** Update the `alloy` Docker container command and configuration (in `services/monitoring/assets/alloy/`) to use the mounted TLS certificate for both its management interface and OTel receivers.
    *   **Local DNS:** Create a local DNS record using the `utils.opnsense.unbound.host_override.HostOverride` component to point `alloy.tobiash.net` to the LoadBalancer IP.

### 2.2. Update `Pulumi.prod.yaml`

Add the configuration for the new `alloy` service to the `prod` stack.

*   **File to edit:** `services/monitoring/Pulumi.prod.yaml`
*   **Action:** Add a new `alloy` section with the required version and other configuration.
    ```yaml
    # renovate: datasource=github-releases packageName=grafana/alloy versioning=semver
    alloy:
      version: v1.10.1 # or latest
    ```

### 2.3. Update `main.py` to deploy the new service

The main entrypoint for the monitoring service needs to be updated to call the new `create_alloy` function.

*   **File to edit:** `services/monitoring/monitoring/main.py`
*   **Change:** Add a call to `create_alloy` from `alloy.py` when deploying the `prod` stack.

## Phase 3: Migration and Finalization

This phase focuses on reconfiguring the `alloy_legacy` service to forward data to the new `alloy` service.

### 3.1. Update `alloy_legacy` configuration

Modify the Alloy configuration files in `services/monitoring/assets/alloy_legacy/` to:
*   Remove any configuration that is now handled by the new `alloy` service.
*   Keep only the local data gathering configuration (e.g., Synology logs).
*   Add a `forward_to` block to send all collected data to the new `alloy` service's OTel receiver endpoint (`alloy.tobiash.net:4317` or similar).

### 3.2. Deploy all changes

Run `pulumi up` for both the `dev` and `prod` stacks to apply all the changes.

*   **`dev` stack:** This will update the `alloy_legacy` service.
*   **`prod` stack:** This will deploy the new `alloy` service.

### 3.3. Verification

After deployment, verify that:
*   The new `alloy` service is running and accessible at `https://alloy.tobiash.net`.
*   The `alloy_legacy` service is running and forwarding data to the new service.
*   Metrics and logs are flowing through the new pipeline into Grafana/Loki/Mimir correctly.

This refined plan should provide a clear path for the refactoring effort.
