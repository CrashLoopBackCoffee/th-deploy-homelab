# Custom image combining restic with rclone for Paperless backups
# This eliminates the need for runtime downloads and improves startup time and reliability

# renovate: datasource=github-releases packageName=restic/restic versioning=semver
ARG RESTIC_VERSION=0.18.0

# renovate: datasource=github-releases packageName=rclone/rclone versioning=semver
ARG BUILD_RCLONE_VERSION=1.70.3

FROM restic/restic:${RESTIC_VERSION}

ARG BUILD_RCLONE_VERSION
ARG TARGETARCH

# Install rclone and clean up in single layer to minimize image size
RUN apk add --no-cache wget unzip && \
    cd /tmp && \
    wget -O rclone.zip "https://github.com/rclone/rclone/releases/download/v${BUILD_RCLONE_VERSION}/rclone-v${BUILD_RCLONE_VERSION}-linux-${TARGETARCH}.zip" && \
    unzip rclone.zip && \
    mv "rclone-v${BUILD_RCLONE_VERSION}-linux-${TARGETARCH}/rclone" /usr/local/bin/ && \
    chmod +x /usr/local/bin/rclone && \
    rm -rf /tmp/rclone* && \
    apk del wget unzip

# Verify installations
RUN restic version && rclone version

# Keep the same entrypoint as the base restic image
