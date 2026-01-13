# Netboot.xyz Service

This service deploys [netboot.xyz](https://netboot.xyz) as a Docker container to the Synology NAS.

## Overview

Netboot.xyz is a way to PXE boot various operating system installers or utilities from one place within the BIOS without the need of having to go retrieve the media to run the tool. It provides a convenient way to boot into a variety of operating systems and utilities using PXE/iPXE.

## Features

- Web interface for managing boot options
- TFTP server for PXE booting
- Support for multiple operating systems and utilities
- Customizable boot menus

## Configuration

The service is configured via `Pulumi.prod.yaml`:

- **version**: The netboot.xyz container image version
- **web-port**: The HTTP port for the web interface (default: 3030)
- **tftp-port**: The TFTP port for PXE booting (default: 69)

## Deployment

```bash
# Preview changes
(cd services/netboot && pulumi preview -s prod --diff --non-interactive)

# Deploy
(cd services/netboot && pulumi up --stack prod --non-interactive --skip-preview)
```

## Access

After deployment, the service is accessible at:
- Web interface: https://netboot.tobiash.net
- TFTP server: netboot.tobiash.net:69 (UDP)
- Mirror HTTP server: http://netboot-mirror.tobiash.net

## Storage

The service uses two persistent volumes on the Synology:
- `/volume2/docker/netboot-config`: Configuration files
- `/volume2/docker/netboot-assets`: Boot assets and custom menus

## OPNSense Configuration

See https://blog.kail.io/running-netbootxyz-from-opnsense.html
