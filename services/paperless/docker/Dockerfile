# Custom image combining restic with rclone for Paperless backups
# This eliminates the need for runtime downloads and improves startup time and reliability

# renovate: datasource=github-releases packageName=restic/restic versioning=semver
ARG RESTIC_VERSION=0.17.3

# renovate: datasource=github-releases packageName=rclone/rclone versioning=semver
ARG RCLONE_VERSION=1.68.2

FROM restic/restic:${RESTIC_VERSION}

ARG RCLONE_VERSION

# Install rclone and clean up in single layer to minimize image size
RUN apk add --no-cache wget unzip && \
    cd /tmp && \
    wget -O rclone.zip "https://github.com/rclone/rclone/releases/download/v${RCLONE_VERSION}/rclone-v${RCLONE_VERSION}-linux-amd64.zip" && \
    unzip rclone.zip && \
    mv "rclone-v${RCLONE_VERSION}-linux-amd64/rclone" /usr/local/bin/ && \
    chmod +x /usr/local/bin/rclone && \
    rm -rf /tmp/rclone* && \
    apk del wget unzip

# Verify installations
RUN restic version && rclone version

# Keep the same entrypoint as the base restic image
