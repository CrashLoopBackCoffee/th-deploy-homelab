#!/bin/bash
set -e

# PostgreSQL Migration Script for Paperless
# This script performs the complete migration from Bitnami PostgreSQL to the new deployment

# Configuration
NAMESPACE="paperless"
OLD_POSTGRES_POD="postgres-0"  # Bitnami StatefulSet pod name
NEW_POSTGRES_SERVICE="paperless-postgres-rw"  # CloudNativePG service name
BACKUP_DIR="/tmp/postgres-migration"
BACKUP_FILE="paperless_backup_$(date +%Y%m%d_%H%M%S).sql"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not available"
        exit 1
    fi

    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi

    # Check if old PostgreSQL pod exists
    if ! kubectl get pod "$OLD_POSTGRES_POD" -n "$NAMESPACE" &> /dev/null; then
        log_error "Old PostgreSQL pod $OLD_POSTGRES_POD does not exist in namespace $NAMESPACE"
        exit 1
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"

    log_info "Prerequisites check passed"
}

backup_database() {
    log_info "Creating backup of current database..."

    # Create full backup
    kubectl exec -n "$NAMESPACE" "$OLD_POSTGRES_POD" -- pg_dumpall -U postgres > "$BACKUP_DIR/full_$BACKUP_FILE"
    if [ $? -ne 0 ]; then
        log_error "Failed to create full database backup"
        exit 1
    fi

    # Create paperless-specific backup
    kubectl exec -n "$NAMESPACE" "$OLD_POSTGRES_POD" -- pg_dump -U postgres --clean --if-exists paperless > "$BACKUP_DIR/$BACKUP_FILE"
    if [ $? -ne 0 ]; then
        log_error "Failed to create paperless database backup"
        exit 1
    fi

    # Verify backup
    if [ ! -s "$BACKUP_DIR/$BACKUP_FILE" ]; then
        log_error "Backup file is empty"
        exit 1
    fi

    local backup_size=$(du -h "$BACKUP_DIR/$BACKUP_FILE" | cut -f1)
    log_info "Backup created successfully: $BACKUP_FILE ($backup_size)"

    # Create backup verification info
    kubectl exec -n "$NAMESPACE" "$OLD_POSTGRES_POD" -- psql -U postgres -d paperless -c "SELECT COUNT(*) as document_count FROM documents_document;" > "$BACKUP_DIR/verification_info.txt"
    kubectl exec -n "$NAMESPACE" "$OLD_POSTGRES_POD" -- psql -U postgres -d paperless -c "SELECT COUNT(*) as tag_count FROM documents_tag;" >> "$BACKUP_DIR/verification_info.txt"

    log_info "Backup verification info saved"
}

stop_paperless() {
    log_info "Stopping Paperless application..."

    # Scale down Paperless deployment
    kubectl scale deployment paperless -n "$NAMESPACE" --replicas=0
    if [ $? -ne 0 ]; then
        log_warn "Failed to scale down Paperless deployment (may not exist yet)"
    fi

    # Wait for pods to terminate
    log_info "Waiting for Paperless pods to terminate..."
    kubectl wait --for=delete pod -l app=paperless -n "$NAMESPACE" --timeout=120s

    log_info "Paperless application stopped"
}

wait_for_new_postgres() {
    log_info "Waiting for new PostgreSQL to be ready..."

    # Wait for service to be available
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if kubectl get service "$NEW_POSTGRES_SERVICE" -n "$NAMESPACE" &> /dev/null; then
            log_info "New PostgreSQL service is available"
            break
        fi

        log_info "Waiting for new PostgreSQL service... (attempt $((attempt + 1))/$max_attempts)"
        sleep 10
        attempt=$((attempt + 1))
    done

    if [ $attempt -eq $max_attempts ]; then
        log_error "New PostgreSQL service did not become available within timeout"
        exit 1
    fi

    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to accept connections..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=paperless-postgres -n "$NAMESPACE" --timeout=300s

    log_info "New PostgreSQL is ready"
}

restore_database() {
    log_info "Restoring database to new PostgreSQL..."

    # Get the new PostgreSQL pod name
    local new_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=paperless-postgres -o jsonpath='{.items[0].metadata.name}')

    if [ -z "$new_pod" ]; then
        log_error "Could not find new PostgreSQL pod"
        exit 1
    fi

    log_info "Restoring to pod: $new_pod"

    # Restore the database
    kubectl exec -i -n "$NAMESPACE" "$new_pod" -- psql -U paperless -d paperless < "$BACKUP_DIR/$BACKUP_FILE"
    if [ $? -ne 0 ]; then
        log_error "Failed to restore database"
        exit 1
    fi

    log_info "Database restored successfully"
}

verify_migration() {
    log_info "Verifying migration..."

    # Get the new PostgreSQL pod name
    local new_pod=$(kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/name=paperless-postgres -o jsonpath='{.items[0].metadata.name}')

    # Check document count
    local new_doc_count=$(kubectl exec -n "$NAMESPACE" "$new_pod" -- psql -U paperless -d paperless -t -c "SELECT COUNT(*) FROM documents_document;" | tr -d ' ')
    local new_tag_count=$(kubectl exec -n "$NAMESPACE" "$new_pod" -- psql -U paperless -d paperless -t -c "SELECT COUNT(*) FROM documents_tag;" | tr -d ' ')

    log_info "New database statistics:"
    log_info "  Documents: $new_doc_count"
    log_info "  Tags: $new_tag_count"

    # Compare with backup info
    if [ -f "$BACKUP_DIR/verification_info.txt" ]; then
        log_info "Comparing with original database..."
        cat "$BACKUP_DIR/verification_info.txt"
    fi

    log_info "Migration verification completed"
}

start_paperless() {
    log_info "Starting Paperless application..."

    # Scale up Paperless deployment
    kubectl scale deployment paperless -n "$NAMESPACE" --replicas=1
    if [ $? -ne 0 ]; then
        log_error "Failed to scale up Paperless deployment"
        exit 1
    fi

    # Wait for deployment to be ready
    kubectl wait --for=condition=available deployment/paperless -n "$NAMESPACE" --timeout=300s
    if [ $? -ne 0 ]; then
        log_error "Paperless deployment did not become available"
        exit 1
    fi

    log_info "Paperless application started successfully"
}

cleanup_old_postgres() {
    log_warn "Cleanup of old PostgreSQL deployment should be done manually"
    log_warn "Run: pulumi destroy on the old postgres resources after confirming everything works"
    log_warn "Old backup files are preserved in: $BACKUP_DIR"
}

rollback() {
    log_error "Migration failed. Starting rollback..."

    # Stop new Paperless if running
    kubectl scale deployment paperless -n "$NAMESPACE" --replicas=0 2>/dev/null || true

    # Start old Paperless
    log_info "Restarting Paperless with old database..."
    kubectl scale deployment paperless -n "$NAMESPACE" --replicas=1

    log_info "Rollback completed. Check application status."
}

main() {
    log_info "Starting PostgreSQL migration for Paperless"
    log_info "Backup directory: $BACKUP_DIR"

    # Set up error handling
    trap rollback ERR

    # Execute migration steps
    check_prerequisites
    backup_database
    stop_paperless
    wait_for_new_postgres
    restore_database
    verify_migration
    start_paperless
    cleanup_old_postgres

    log_info "PostgreSQL migration completed successfully!"
    log_info "Backup files are preserved in: $BACKUP_DIR"
    log_info "Please test the Paperless application thoroughly before removing old resources."
}

# Script execution
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
