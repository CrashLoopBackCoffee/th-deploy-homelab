---
name: opentelemetry-alloy-config
description: Guidelines for writing and editing Grafana Alloy OpenTelemetry pipeline configuration files in this repository. Use this when creating or modifying *.alloy files related to OpenTelemetry collection, processing, or export.
license: MIT
---

## File Naming Convention

Each Alloy config file has a prefix that reflects its role in the pipeline:

| Prefix | Phase | Description |
|---|---|---|
| `collect_*.alloy` | **Ingestion** | Receives telemetry from external sources (OTLP receiver, log collectors, Prometheus scrapers) and forwards into the processing pipeline. |
| `discovery_*.alloy` | **Discovery** | Discovers and relabels Prometheus scrape targets. Not part of the OTel pipeline itself. |
| `process_otel.alloy` | **Processing** | Central OTel pipeline shared by all signals (metrics, logs, traces). |
| `export_*.alloy` | **Export** | Sends processed telemetry to a backend (Mimir, Grafana Cloud, upstream Alloy). |
| `http_tls.alloy`, `logging.alloy`, `live_debugging.alloy` | **Support** | Infrastructure configuration. |

## Pipeline Flow

```
collect_*.alloy  ─►  process_otel.alloy  ─►  export_*.alloy
```

Every `collect_*.alloy` component must forward its output to `otelcol.processor.resourcedetection.default.input` as the single entry point into `process_otel.alloy`.

## Standard Processor Chain in `process_otel.alloy`

1. `otelcol.processor.resourcedetection "default"` — auto-detects `env` and `system` resource attributes.
2. `otelcol.processor.transform "..."` — normalize / set `service.name` and similar attributes.
3. `otelcol.processor.transform "drop_unneeded_resource_attributes"` — removes noisy process/OS attributes.
4. `otelcol.processor.transform "add_resource_attributes_as_metric_attributes"` *(metrics only)* — promotes resource attributes (e.g. `deployment.environment`, `service.version`) to metric datapoint labels.
5. `otelcol.processor.batch "default"` — batches all signals before export.

## OTTL Syntax — Resource Context

When `context = "resource"` inside an `otelcol.processor.transform` block, use `attributes[...]` to access resource attributes directly. Do **not** prefix with `resource.`:

```alloy
// CORRECT — context is "resource", so attributes[] refers to resource attributes
otelcol.processor.transform "drop_unneeded_resource_attributes" {
    trace_statements {
        context    = "resource"
        statements = ["delete_key(attributes, \"os.type\")"]
    }
}

// INCORRECT — resource.attributes[] is redundant when context is already "resource"
otelcol.processor.transform "drop_unneeded_resource_attributes" {
    trace_statements {
        context    = "resource"
        statements = ["delete_key(resource.attributes, \"os.type\")"]
    }
}
```

When the context is `"log"`, `"metric"`, or `"datapoint"`, resource attributes are accessed via `resource.attributes[...]`.

## Service Deployments

| Directory | Environment | Description |
|---|---|---|
| `services/monitoring/assets/alloy/` | prod (Kubernetes) | Full pipeline: Mimir (metrics) + Grafana Cloud (traces, logs) |
| `services/monitoring/assets/alloy_legacy/` | dev (Docker/Synology) | Legacy collector; forwards to main Alloy via OTLP |
| `services/iot/assets/alloy/` | prod (IoT host) | Collects Docker + journal logs; forwards to main Alloy via OTLP |
