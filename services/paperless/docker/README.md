# Custom Restic+Rclone Docker Image

This directory contains a custom Docker image that combines [restic](https://restic.net/) with [rclone](https://rclone.org/) for the Paperless backup system.

## Purpose

The custom image eliminates the need for runtime downloads of rclone, providing several benefits:

- **Faster startup**: No need to download ~24MB rclone binary on every pod restart
- **Better reliability**: No external dependencies during pod initialization
- **Improved security**: Pre-vetted binaries instead of runtime downloads
- **Version consistency**: Reproducible builds with pinned versions
- **Offline capability**: No internet required during container startup

## Components

- **Base image**: `restic/restic:0.17.3` (configurable via Renovate)
- **Added component**: `rclone v1.68.2` (configurable via Renovate)
- **Architecture**: `linux/amd64` and `linux/arm64`

## Build Process

The image is automatically built and published to GitHub Container Registry via GitHub Actions when:

- Changes are made to this directory
- Changes are made to the Paperless configuration
- The workflow file is updated

### Image Tags

- `latest`: Latest build from main branch
- `restic-X.Y.Z-rclone-A.B.C`: Version-specific tag

## Usage

The image is used in the Paperless StatefulSet as the `restic` sidecar container:

```yaml
containers:
  - name: restic
    image: ghcr.io/crashloopbackcoffee/restic-rclone:restic-0.17.3-rclone-1.68.2
    # ... rest of container spec
```

## Renovate Integration

Both base components are automatically updated via Renovate:

```dockerfile
# renovate: datasource=github-releases packageName=restic/restic versioning=semver
ARG RESTIC_VERSION=0.17.3

# renovate: datasource=github-releases packageName=rclone/rclone versioning=semver
ARG RCLONE_VERSION=1.68.2
```

## Local Development

To build locally:

```bash
cd services/paperless/docker
docker build \
  --build-arg RESTIC_VERSION=0.17.3 \
  --build-arg RCLONE_VERSION=1.68.2 \
  -t local/restic-rclone .
```

To test the image:

```bash
# Check versions
docker run --rm local/restic-rclone restic version
docker run --rm local/restic-rclone rclone version

# Interactive shell
docker run --rm -it local/restic-rclone /bin/sh
```
