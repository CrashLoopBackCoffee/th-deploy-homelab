#!/bin/bash

################################################################################
# Standalone Synology DSM Certificate Deployment Script
################################################################################
# A pure bash/curl implementation for uploading certificates to Synology DSM
# Designed to run in Kubernetes cronjobs without acme.sh dependencies
#
# Environment Variables:
#   Required:
#     SYNO_HOSTNAME       - Synology hostname or IP
#     SYNO_USERNAME       - Admin username
#     SYNO_PASSWORD       - Admin password
#     CERT_KEY_FILE       - Path to certificate private key
#     CERT_CERT_FILE      - Path to certificate file (full chain from cert-manager)
#
#   Optional:
#     SYNO_PORT           - API port (default: 5000)
#     SYNO_SCHEME         - http or https (default: http)
#     SYNO_CERTIFICATE    - Certificate description to update/create (default: empty)
#     CERT_CA_FILE        - Path to separate CA file (optional, uses CERT_CERT_FILE if not set)
#     DEBUG               - Set to "1" for verbose output
#
# Exit Codes:
#   0 - Success
#   1 - Authentication failure
#   2 - Certificate file error
#   3 - API error
#   4 - Configuration error
################################################################################

set -eo pipefail

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*" >&2
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

log_debug() {
    if [ "${DEBUG:-0}" = "1" ]; then
        echo -e "[DEBUG] $*" >&2
    fi
}

# URL encode function
url_encode() {
    local string="$1"
    local strlen=${#string}
    local encoded=""
    local pos c o

    for (( pos=0 ; pos<strlen ; pos++ )); do
        c=${string:$pos:1}
        case "$c" in
            [-_.~a-zA-Z0-9] ) o="${c}" ;;
            * ) printf -v o '%%%02x' "'$c"
        esac
        encoded+="${o}"
    done
    echo "${encoded}"
}

# Validate required files
validate_files() {
    local missing=0

    if [ -z "${CERT_KEY_FILE}" ] || [ ! -f "${CERT_KEY_FILE}" ]; then
        log_error "Certificate key file not found: ${CERT_KEY_FILE}"
        missing=1
    fi

    if [ -z "${CERT_CERT_FILE}" ] || [ ! -f "${CERT_CERT_FILE}" ]; then
        log_error "Certificate file not found: ${CERT_CERT_FILE}"
        missing=1
    fi

    # CA file is optional - if not provided, use the cert file (which should be full chain)
    if [ -n "${CERT_CA_FILE}" ] && [ ! -f "${CERT_CA_FILE}" ]; then
        log_error "CA certificate file specified but not found: ${CERT_CA_FILE}"
        missing=1
    fi

    if [ $missing -eq 1 ]; then
        return 2
    fi
}

# Validate required configuration
validate_config() {
    if [ -z "${SYNO_USERNAME}" ] || [ -z "${SYNO_PASSWORD}" ]; then
        log_error "SYNO_USERNAME and SYNO_PASSWORD must be set"
        return 4
    fi

    if [ -z "${SYNO_HOSTNAME}" ]; then
        log_error "SYNO_HOSTNAME must be set"
        return 4
    fi
}

# Get API info
get_api_info() {
    local base_url="$1"
    local response

    log_info "Discovering Synology DSM API information..."
    response=$(curl -sk "${base_url}/webapi/query.cgi?api=SYNO.API.Info&version=1&method=query&query=SYNO.API.Auth" 2>&1)

    if [ $? -ne 0 ]; then
        log_error "Failed to connect to Synology DSM API"
        log_debug "Response: ${response}"
        return 3
    fi

    api_path=$(echo "${response}" | grep -o '"SYNO.API.Auth"[^}]*' | grep -o '"path":"[^"]*"' | cut -d'"' -f4)
    api_version=$(echo "${response}" | grep -o '"SYNO.API.Auth"[^}]*' | grep -o '"maxVersion":[0-9]*' | grep -o '[0-9]*')

    log_debug "API Path: ${api_path}"
    log_debug "API Version: ${api_version}"

    if [ -z "${api_path}" ] || [ -z "${api_version}" ]; then
        log_error "Failed to discover API information"
        log_debug "Response: ${response}"
        return 3
    fi

    echo "${api_path}|${api_version}"
}

# Login to DSM
login() {
    local base_url="$1"
    local api_path="$2"
    local api_version="$3"
    local encoded_username encoded_password
    local response error_code

    encoded_username=$(url_encode "${SYNO_USERNAME}")
    encoded_password=$(url_encode "${SYNO_PASSWORD}")

    log_info "Authenticating to Synology DSM at ${SYNO_HOSTNAME}:${SYNO_PORT}..."

    response=$(curl -sk "${base_url}/webapi/${api_path}?api=SYNO.API.Auth&version=${api_version}&method=login&format=sid&account=${encoded_username}&passwd=${encoded_password}&enable_syno_token=yes" 2>&1)

    log_debug "Login response: ${response}"

    error_code=$(echo "${response}" | grep -o '"code":[0-9]*' | head -1 | grep -o '[0-9]*')

    # Check for errors
    if [ -n "${error_code}" ]; then
        case "${error_code}" in
            400)
                log_error "Authentication failed: Invalid username or password"
                ;;
            401)
                log_error "Authentication failed: Account does not exist"
                ;;
            403)
                log_error "Authentication failed: 2FA is enabled - please disable 2FA for this account"
                ;;
            406)
                log_error "Authentication failed: 2FA required but not configured"
                ;;
            408|409|410)
                log_error "Authentication failed: Password expired or must be changed"
                ;;
            *)
                log_error "Authentication failed with error code: ${error_code}"
                ;;
        esac
        return 1
    fi

    # Extract session ID and token
    local sid token
    sid=$(echo "${response}" | grep -o '"sid":"[^"]*"' | cut -d'"' -f4)
    token=$(echo "${response}" | grep -o '"synotoken":"[^"]*"' | cut -d'"' -f4)

    if [ -z "${sid}" ] || [ -z "${token}" ]; then
        log_error "Failed to obtain session ID and token"
        log_debug "Response: ${response}"
        return 1
    fi

    log_info "Authentication successful"
    log_debug "Session ID: ${sid}"
    log_debug "Token: ${token}"

    echo "${sid}|${token}"
}

# Logout from DSM
logout() {
    local base_url="$1"
    local api_path="$2"
    local api_version="$3"
    local sid="$4"

    log_debug "Logging out..."
    curl -sk "${base_url}/webapi/${api_path}?api=SYNO.API.Auth&version=${api_version}&method=logout&_sid=${sid}" >/dev/null 2>&1 || true
}

# Get certificate list and find ID
get_certificate_id() {
    local base_url="$1"
    local sid="$2"
    local token="$3"
    local cert_desc="$4"
    local response error_code

    log_info "Fetching certificate list from Synology DSM..."
    response=$(curl -sk -X POST \
        -H "X-SYNO-TOKEN: ${token}" \
        "${base_url}/webapi/entry.cgi" \
        -d "api=SYNO.Core.Certificate.CRT&method=list&version=1&_sid=${sid}" 2>&1)

    log_debug "Certificate list response: ${response}"

    error_code=$(echo "${response}" | grep -o '"code":[0-9]*' | head -1 | grep -o '[0-9]*')

    if [ -n "${error_code}" ]; then
        if [ "${error_code}" = "105" ]; then
            log_error "Insufficient permissions: User must be administrator"
        else
            log_error "Failed to fetch certificate list (error code: ${error_code})"
        fi
        return 3
    fi

    # Escape certificate description for grep
    local escaped_desc
    escaped_desc=$(echo "${cert_desc}" | sed 's/[]\/$*.^[]/\\&/g' | sed 's/"/\\"/g')

    # Try to find certificate ID by description
    local cert_id is_default
    cert_id=$(echo "${response}" | grep -o "\"desc\":\"${escaped_desc}\"[^}]*\"id\":\"[^\"]*\"" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

    if [ -n "${cert_id}" ]; then
        log_info "Found existing certificate: ${cert_desc} (ID: ${cert_id})"

        # Check if it's the default certificate
        is_default=$(echo "${response}" | grep -o "\"desc\":\"${escaped_desc}\"[^}]*\"is_default\":true" || echo "")

        echo "${cert_id}|${is_default}"
    else
        log_info "Certificate '${cert_desc}' not found - will create new one"
        echo "|"
    fi
}

# Split certificate chain into server cert and intermediate certs
split_certificate_chain() {
    local cert_file="$1"
    local output_type="$2"  # "server" or "intermediate"

    # Read the full certificate chain
    local cert_content
    cert_content=$(cat "${cert_file}")

    if [ "${output_type}" = "server" ]; then
        # Extract first certificate (server certificate)
        echo "${cert_content}" | awk '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/ {print; if (/-----END CERTIFICATE-----/) exit}'
    else
        # Extract everything after the first certificate (intermediate/CA chain)
        echo "${cert_content}" | awk '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/ {if (found) print} /-----END CERTIFICATE-----/ {found=1}'
    fi
}

# Upload certificate to DSM
upload_certificate() {
    local base_url="$1"
    local sid="$2"
    local token="$3"
    local cert_id="$4"
    local cert_desc="$5"
    local is_default="$6"
    local response

    log_info "Preparing certificate upload..."

    # Generate boundary for multipart form data
    local boundary="----WebKitFormBoundary$(date +%s)$(( RANDOM ))"
    local nl=$'\r\n'

    # Build multipart form data
    local form_data=""

    # Add key file
    form_data+="--${boundary}${nl}"
    form_data+="Content-Disposition: form-data; name=\"key\"; filename=\"$(basename "${CERT_KEY_FILE}")\"${nl}"
    form_data+="Content-Type: application/octet-stream${nl}${nl}"
    form_data+="$(cat "${CERT_KEY_FILE}")${nl}"

    # Split certificate chain and add server certificate
    local server_cert intermediate_cert
    if [ -n "${CERT_CA_FILE}" ]; then
        # If CA file provided separately, use cert file as-is
        server_cert=$(cat "${CERT_CERT_FILE}")
        intermediate_cert=$(cat "${CERT_CA_FILE}")
    else
        # Split the full chain from cert-manager
        log_debug "Splitting certificate chain from ${CERT_CERT_FILE}"
        server_cert=$(split_certificate_chain "${CERT_CERT_FILE}" "server")
        intermediate_cert=$(split_certificate_chain "${CERT_CERT_FILE}" "intermediate")
    fi

    # Add server certificate
    form_data+="--${boundary}${nl}"
    form_data+="Content-Disposition: form-data; name=\"cert\"; filename=\"cert.pem\"${nl}"
    form_data+="Content-Type: application/octet-stream${nl}${nl}"
    form_data+="${server_cert}${nl}"

    # Add intermediate/CA certificates
    form_data+="--${boundary}${nl}"
    form_data+="Content-Disposition: form-data; name=\"inter_cert\"; filename=\"chain.pem\"${nl}"
    form_data+="Content-Type: application/octet-stream${nl}${nl}"
    form_data+="${intermediate_cert}${nl}"

    # Add certificate ID
    form_data+="--${boundary}${nl}"
    form_data+="Content-Disposition: form-data; name=\"id\"${nl}${nl}"
    form_data+="${cert_id}${nl}"

    # Add certificate description
    form_data+="--${boundary}${nl}"
    form_data+="Content-Disposition: form-data; name=\"desc\"${nl}${nl}"
    form_data+="${cert_desc}${nl}"

    # Add as_default if this was the default certificate
    if [ -n "${is_default}" ]; then
        form_data+="--${boundary}${nl}"
        form_data+="Content-Disposition: form-data; name=\"as_default\"${nl}${nl}"
        form_data+="true${nl}"
    fi

    form_data+="--${boundary}--${nl}"

    log_info "Uploading certificate to Synology DSM..."
    response=$(curl -sk -X POST \
        -H "X-SYNO-TOKEN: ${token}" \
        -H "Content-Type: multipart/form-data; boundary=${boundary}" \
        --data-binary "${form_data}" \
        "${base_url}/webapi/entry.cgi?api=SYNO.Core.Certificate&method=import&version=1&SynoToken=${token}&_sid=${sid}" 2>&1)

    log_debug "Upload response: ${response}"

    # Check for errors
    if echo "${response}" | grep -q '"error":'; then
        log_error "Failed to upload certificate"
        log_debug "Response: ${response}"
        return 3
    fi

    # Check if HTTP services need restart
    if echo "${response}" | grep -q '"restart_httpd":true'; then
        log_info "Certificate uploaded successfully - HTTP services will restart"
    else
        log_info "Certificate uploaded successfully"
    fi

    return 0
}

# Main execution
main() {
    log_info "Starting Synology DSM certificate deployment"

    # Set defaults
    SYNO_SCHEME="${SYNO_SCHEME:-http}"
    SYNO_HOSTNAME="${SYNO_HOSTNAME:-localhost}"
    SYNO_PORT="${SYNO_PORT:-5000}"
    SYNO_CERTIFICATE="${SYNO_CERTIFICATE:-}"

    # Validate configuration
    validate_config || return $?
    validate_files || return $?

    # Build base URL
    local base_url="${SYNO_SCHEME}://${SYNO_HOSTNAME}:${SYNO_PORT}"
    log_debug "Base URL: ${base_url}"

    # Get API information
    local api_info api_path api_version
    api_info=$(get_api_info "${base_url}") || return $?
    api_path=$(echo "${api_info}" | cut -d'|' -f1)
    api_version=$(echo "${api_info}" | cut -d'|' -f2)

    # Login
    local auth_info sid token
    auth_info=$(login "${base_url}" "${api_path}" "${api_version}") || return $?
    sid=$(echo "${auth_info}" | cut -d'|' -f1)
    token=$(echo "${auth_info}" | cut -d'|' -f2)

    # Get certificate ID (if description provided)
    local cert_id="" is_default=""
    if [ -n "${SYNO_CERTIFICATE}" ]; then
        local cert_info
        cert_info=$(get_certificate_id "${base_url}" "${sid}" "${token}" "${SYNO_CERTIFICATE}")
        cert_id=$(echo "${cert_info}" | cut -d'|' -f1)
        is_default=$(echo "${cert_info}" | cut -d'|' -f2)
    fi

    # Upload certificate (will create if cert_id is empty)
    upload_certificate "${base_url}" "${sid}" "${token}" "${cert_id}" "${SYNO_CERTIFICATE}" "${is_default}"
    local upload_result=$?

    # Logout
    logout "${base_url}" "${api_path}" "${api_version}" "${sid}"

    if [ ${upload_result} -eq 0 ]; then
        log_info "Certificate deployment completed successfully"
        return 0
    else
        log_error "Certificate deployment failed"
        return ${upload_result}
    fi
}

# Run main function
main "$@"
