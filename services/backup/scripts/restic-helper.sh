#!/bin/bash
set -euo pipefail

# Restic Helper Script
# This script sets up the environment to run restic commands locally
# for checking and restoring backups from the backup service

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <volume-name> <command> [args...]"
    echo ""
    echo "Available volumes:"
    echo "  joplin       - Joplin notes backup"
    echo "  paperless    - Paperless documents backup (if configured)"
    echo ""
    echo "Common commands:"
    echo "  snapshots                    - List all snapshots"
    echo "  check                        - Check repository integrity"
    echo "  stats                        - Show repository statistics"
    echo "  ls latest                    - List files in latest snapshot"
    echo "  restore <snapshot-id> --target /path/to/restore"
    echo "  mount /mnt/point             - Mount repository as filesystem"
    echo ""
    echo "Examples:"
    echo "  $0 joplin snapshots"
    echo "  $0 joplin check"
    echo "  $0 joplin restore latest --target ./restored-files"
    echo "  $0 joplin ls latest | grep important-file"
    echo ""
    echo "Environment setup:"
    echo "  Set RESTIC_PASSWORD_FILE or RESTIC_PASSWORD"
    echo "  Set S3 credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT)"
    exit 1
}

setup_environment() {
    local volume_name="$1"

    # Volume-specific bucket mapping
    case "$volume_name" in
        "joplin")
            export RESTIC_REPOSITORY="s3:${AWS_S3_ENDPOINT}/restic-joplin"
            ;;
        "schule")
            export RESTIC_REPOSITORY="s3:${AWS_S3_ENDPOINT}/restic-schule"
            ;;
        *)
            echo -e "${RED}Error: Unknown volume '$volume_name'${NC}" >&2
            echo "Run '$0' without arguments to see available volumes." >&2
            exit 1
            ;;
    esac

    # Set restic configuration
    export RESTIC_COMPRESSION="max"
    export RESTIC_PACK_SIZE="64M"

    echo -e "${BLUE}Repository:${NC} $RESTIC_REPOSITORY"
}


check_dependencies() {
    if ! command -v restic &> /dev/null; then
        echo -e "${RED}Error: restic is not installed or not in PATH${NC}" >&2
        echo "Install restic: https://restic.readthedocs.io/en/latest/020_installation.html" >&2
        exit 1
    fi

    if ! command -v op &> /dev/null; then
        echo -e "${RED}Error: 1Password CLI (op) is not installed or not in PATH${NC}" >&2
        echo "Install 1Password CLI: https://developer.1password.com/docs/cli/get-started/" >&2
        echo "Make sure you're signed in: op account list" >&2
        exit 1
    fi
}

load_credentials_from_1password() {
    echo -e "${BLUE}Loading credentials from 1Password...${NC}"

    # Use op inject to batch load all credentials in one operation
    # This is much more efficient than multiple op read calls
    eval $(cat <<EOF | op inject
export AWS_S3_ENDPOINT="{{ op://Pulumi/IDrive E2 Backup/Endpoint }}"
export AWS_ACCESS_KEY_ID="{{ op://Pulumi/IDrive E2 Backup/Access Key ID }}"
export AWS_SECRET_ACCESS_KEY="{{ op://Pulumi/IDrive E2 Backup/Secret Access Key }}"
export RESTIC_PASSWORD="{{ op://Pulumi/Restic Backup/password }}"
EOF
)

    echo -e "${GREEN}Credentials loaded successfully!${NC}"
}

check_credentials() {
    # Try to load from 1Password if not already set
    if [[ -z "${AWS_S3_ENDPOINT:-}" || -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" || -z "${RESTIC_PASSWORD:-}" ]]; then
        load_credentials_from_1password
    fi

    # Verify all credentials are now available
    local missing_vars=()

    if [[ -z "${AWS_S3_ENDPOINT:-}" ]]; then
        missing_vars+=("AWS_S3_ENDPOINT")
    fi
    if [[ -z "${AWS_ACCESS_KEY_ID:-}" ]]; then
        missing_vars+=("AWS_ACCESS_KEY_ID")
    fi
    if [[ -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
        missing_vars+=("AWS_SECRET_ACCESS_KEY")
    fi
    if [[ -z "${RESTIC_PASSWORD:-}" ]]; then
        missing_vars+=("RESTIC_PASSWORD")
    fi

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo -e "${RED}Error: Failed to load required credentials:${NC}" >&2
        printf '  %s\n' "${missing_vars[@]}" >&2
        echo "" >&2
        echo "Make sure you're signed in to 1Password CLI:" >&2
        echo "  op account list" >&2
        echo "  op signin" >&2
        echo "" >&2
        echo "Or set environment variables manually:" >&2
        echo "  export AWS_S3_ENDPOINT='https://your-endpoint'" >&2
        echo "  export AWS_ACCESS_KEY_ID='your-access-key'" >&2
        echo "  export AWS_SECRET_ACCESS_KEY='your-secret-key'" >&2
        echo "  export RESTIC_PASSWORD='your-restic-password'" >&2
        exit 1
    fi
}

main() {
    if [[ $# -lt 2 ]]; then
        usage
    fi

    local volume_name="$1"
    shift

    check_dependencies
    check_credentials
    setup_environment "$volume_name"

    echo -e "${GREEN}Running:${NC} restic $*"
    echo ""

    # Execute restic with all remaining arguments
    exec restic "$@"
}

# Load .env file if it exists
if [[ -f "$SERVICE_DIR/.env" ]]; then
    echo -e "${YELLOW}Loading environment from .env file${NC}"
    # shellcheck source=/dev/null
    source "$SERVICE_DIR/.env"
fi

main "$@"
