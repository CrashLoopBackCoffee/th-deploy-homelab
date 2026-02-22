---
name: homelab-ingress
description: Guidelines for exposing Kubernetes services in this homelab. Use when adding a new service, choosing an ingress method, or implementing DNS, TLS, or public access for a service.
license: MIT
---

## Overview

Every service must first choose one of the three **LAN ingress methods** to make it
reachable within the homelab network. Optionally, the
[Cloudflare Tunnel](#4-cloudflare-tunnel-public-access-addon) can be added on top to
expose the service on the public internet.

| Method | Use when | TLS | Access |
|--------|----------|-----|--------|
| [Traefik IngressRoute](#1-traefik-ingressroute-preferred-for-web-services) | HTTP/HTTPS web UI | Wildcard cert (automatic) | LAN only |
| [MetalLB with cert-manager](#2-metallb-loadbalancer-with-cert-manager-tls) | Non-HTTP protocols or direct-IP HTTPS | Per-service cert | LAN only |
| [MetalLB without TLS](#3-metallb-loadbalancer-without-tls) | Internal metrics, plain TCP/UDP | None | LAN only |
| [Cloudflare Tunnel](#4-cloudflare-tunnel-public-access-addon) *(addon)* | Public internet access | Cloudflare-managed | Public + LAN |

DNS for LAN access is always set up via **OPNsense Unbound host overrides** using
`utils.opnsense.unbound.host_override.HostOverride`. LAN clients always resolve the
service to its local IP (Traefik or MetalLB), so traffic never traverses Cloudflare
from inside the network — even for services that also have a Cloudflare Tunnel.

---

## 1. Traefik IngressRoute (preferred for web services)

Use for all standard HTTPS web UIs. A single Traefik LoadBalancer IP handles all
host-based routing. The wildcard certificate (`*.tobiash.net`) issued by cert-manager
is set as Traefik's default, so `'tls': {}` in the IngressRoute automatically uses it.

**Services using this pattern:** n8n, paperless, immich, tandoor, netbox, ollama, svn.

### DNS setup

Resolve the Traefik service IP, then point the hostname at it:

```python
import utils.opnsense.unbound.host_override

traefik_service = k8s.core.v1.Service.get(
    'traefik-service', 'traefik/traefik', opts=k8s_opts
)
record = utils.opnsense.unbound.host_override.HostOverride(
    'myapp',
    host='myapp',
    domain=component_config.cloudflare.zone,
    record_type='A',
    ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
)
```

### IngressRoute resource

```python
fqdn = f'myapp.{component_config.cloudflare.zone}'
k8s.apiextensions.CustomResource(
    'ingress',
    api_version='traefik.io/v1alpha1',
    kind='IngressRoute',
    metadata={
        'name': 'ingress',
        'namespace': namespace.metadata.name,
    },
    spec={
        'entryPoints': ['websecure'],
        'routes': [
            {
                'kind': 'Rule',
                'match': p.Output.concat('Host(`', fqdn, '`)'),
                'services': [
                    {
                        'name': service.metadata.name,
                        'namespace': service.metadata.namespace,
                        'port': MY_APP_PORT,
                    },
                ],
            }
        ],
        'tls': {},  # uses Traefik's default wildcard certificate
    },
    opts=k8s_opts,
)
```

### URL export

```python
p.export('myapp_url', p.Output.format('https://{}.{}', record.host, record.domain))
```

---

## 2. MetalLB LoadBalancer with cert-manager TLS

Use when the service needs its own TLS certificate — for example, Grafana (HTTPS with
`external_traffic_policy: Local`), Alloy (multiple ports including gRPC), or Mosquitto
(MQTTS). MetalLB assigns an IP from the pool `192.168.40.70`–`192.168.40.99`.

**Services using this pattern:** grafana, alloy, mosquitto.

### cert-manager Certificate resource

```python
certificate = k8s.apiextensions.CustomResource(
    'certificate',
    api_version='cert-manager.io/v1',
    kind='Certificate',
    metadata={
        'name': 'myapp-tls',
        'namespace': namespace.metadata.name,
        'annotations': {
            'pulumi.com/waitFor': 'condition=Ready=True',
        },
    },
    spec={
        'secretName': 'myapp-tls',
        'dnsNames': [component_config.myapp.hostname],
        'issuerRef': {'name': 'lets-encrypt', 'kind': 'ClusterIssuer'},
    },
    opts=k8s_opts,
)
```

Mount the secret into the pod and configure the application to serve TLS directly.

### LoadBalancer Service

```python
service = k8s.core.v1.Service(
    'myapp',
    metadata={
        'namespace': namespace.metadata.name,
        'name': 'myapp',
    },
    spec={
        'type': 'LoadBalancer',
        'selector': app_labels,
        'ports': [
            {
                'name': 'https',
                'port': 443,
                'target_port': MY_APP_PORT,
                'protocol': 'TCP',
            },
        ],
    },
    opts=k8s_opts,
)
```

### DNS setup

Point the hostname directly at the service's LoadBalancer IP:

```python
import utils.opnsense.unbound.host_override

def _create_dns(lb_ip: str) -> None:
    utils.opnsense.unbound.host_override.HostOverride(
        'myapp-host-override',
        host=component_config.myapp.hostname.split('.')[0],
        domain='.'.join(component_config.myapp.hostname.split('.')[1:]),
        record_type='A',
        ipaddress=lb_ip,
    )

service.status.load_balancer.ingress[0].ip.apply(
    lambda ip: _create_dns(ip) if ip else None
)
```

---

## 3. MetalLB LoadBalancer without TLS

Use for internal metrics scrapers, plain TCP/UDP protocols, or other non-HTTPS services
where encryption is not needed.

**Services using this pattern:** speedtest exporter, mqtt2prometheus.

```python
service = k8s.core.v1.Service(
    'myapp',
    metadata={
        'namespace': namespace.metadata.name,
        'name': 'myapp',
    },
    spec={
        'type': 'LoadBalancer',
        'selector': app_labels,
        'ports': [
            {
                'name': 'http',
                'port': MY_APP_PORT,
                'target_port': MY_APP_PORT,
                'protocol': 'TCP',
            },
        ],
    },
    opts=k8s_opts,
)

p.export('myapp_ip', service.status.load_balancer.ingress[0].ip)
```

Add an OPNsense host override if a hostname is needed (same pattern as above).

---

## 4. Cloudflare Tunnel (public access addon)

This is always an **addon** on top of one of the three LAN ingress methods above. The
service must already be reachable on the LAN via Traefik or MetalLB before adding a
Cloudflare Tunnel.

The `ingress` Pulumi service (`services/ingress/`) manages a cloudflared tunnel that
proxies traffic from the public internet to the internal Kubernetes service. LAN clients
continue to resolve the hostname to the local IP via OPNsense Unbound and never traverse
Cloudflare, even after a tunnel is added.

**Services using this pattern:** grafana (MetalLB + tunnel), immich (Traefik + tunnel),
strava-sensor (Traefik + tunnel).

### Adding a new public route

Edit `services/ingress/Pulumi.prod.yaml` and add an entry under `cloudflared.ingress`:

```yaml
cloudflared:
  ingress:
    # HTTP backend
    - service: http://myapp.myapp-namespace:8080
      hostname: myapp.tobiash.net

    # HTTPS backend (e.g., Grafana which terminates its own TLS)
    - service: https://myapp.myapp-namespace
      hostname: myapp.tobiash.net
      set-origin-server-name: true  # required when backend uses SNI
```

The `service` value is the internal Kubernetes DNS name: `<svc-name>.<namespace>:<port>`.
The `hostname` must be a subdomain of the configured Cloudflare zone (`tobiash.net`).
Cloudflare DNS records (CNAME to `{tunnel-id}.cfargotunnel.com`) are created automatically
by Pulumi when the stack is deployed.

YAML keys use kebab-case (`set-origin-server-name`) which `LocalBaseModel` maps automatically
to the snake_case Python field (`set_origin_server_name`).

### Configuration model reference

```python
class CloudflareIngressConfig(utils.model.LocalBaseModel):
    service: str              # Internal K8s service URL
    hostname: str             # Public hostname
    set_origin_server_name: bool = False  # YAML key: set-origin-server-name
```

### Local development tunnel

For local development (services not running in K8s), use the `local-cloudflared` list:

```yaml
local-cloudflared:
  - service: http://localhost:8000
    hostname: myapp-dev.tobiash.net
```

After deploying, run the tunnel locally with the exported token:

```bash
cloudflared tunnel --no-autoupdate run --token <local_cloudflared_tunnel_token>
```

---

## Decision Guide

```
Pick a LAN ingress method first:
  Service is HTTP/HTTPS web UI?
    └─ YES → Traefik IngressRoute (simplest, wildcard cert auto-applied)
    └─ NO  → Non-HTTP protocol or needs own certificate?
         └─ YES, needs TLS → MetalLB LoadBalancer + cert-manager Certificate
         └─ NO  → MetalLB LoadBalancer (plain, no TLS)

Then, optionally add public internet access:
  Service must be reachable from the internet?
    └─ YES → Also add a Cloudflare Tunnel entry in services/ingress/Pulumi.prod.yaml
             (LAN clients still bypass Cloudflare via OPNsense DNS)
    └─ NO  → Done; LAN-only access via the method chosen above
```

---

## Infrastructure Prerequisites

All ingress methods depend on these components managed in `services/kubernetes/`:

- **MetalLB** (`metallb.py`): Provides LoadBalancer IPs from pool `192.168.40.70`–`192.168.40.99`.
- **Traefik** (`traefik.py`): Helm chart in `traefik` namespace; holds a wildcard cert for `*.tobiash.net`.
- **cert-manager** (`certmanager.py`): `ClusterIssuer` named `lets-encrypt` using Cloudflare DNS-01.
- **OPNsense Unbound**: Internal DNS; managed via `utils.opnsense.unbound.host_override.HostOverride`.
