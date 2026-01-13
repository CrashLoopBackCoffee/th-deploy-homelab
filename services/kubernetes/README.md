# Microk8s

The kubernetes service is provided by [MicroK8s](https://microk8s.io/), a lightweight, single-package Kubernetes distribution developed by Canonical.

## Refresh server certificates

```
# Check server certificates:
sudo microk8s refresh-certs -c

# Refresh specific certificates as needed:
sudo microk8s refresh-certs -e server.crt
sudo microk8s refresh-certs -e front-proxy-client.crt
```
