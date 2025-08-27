#!/bin/bash

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly MAX_RETRIES=3
readonly NODE_START_DELAY=3
readonly NODE_STABILIZE_DELAY=2
readonly HEAVY_LIGHT_DELAY=5
readonly VERIFICATION_DELAY=3

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Function to check if formix CLI is available
check_formix_cli() {
    if ! command -v uv >/dev/null 2>&1; then
        log_error "uv command not found. Please install uv first."
        exit 1
    fi
    
    if ! uv run formix --help >/dev/null 2>&1; then
        log_error "formix CLI not working. Please check your installation."
        exit 1
    fi
}

# Function to cleanup existing nodes with proper confirmation handling
cleanup_existing_nodes() {
    log_info "Checking for existing nodes..."
    
    # First check if there are any nodes
    local node_count
    node_count=$(uv run formix --view 2>/dev/null | grep "│" | grep -v "┌\|├\|└" | wc -l | tr -d ' ' || echo "0")
    
    if [ "$node_count" -gt 0 ]; then
        log_info "Found existing nodes. Cleaning up..."
        # Use printf to send "y\n" to confirm the stop-all operation
        printf "y\n" | uv run formix --stop-all 2>/dev/null || {
            log_warning "Failed to stop nodes cleanly, continuing anyway..."
        }
        sleep 3  # Give time for cleanup
        log_success "Cleanup completed"
    else
        log_info "No existing nodes found"
    fi
}

# Function to create a single node with retries
create_node_with_retries() {
    local node_type=$1
    local node_number=$2
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log_info "Creating $node_type node #$node_number (attempt $attempt/$MAX_RETRIES)..."
        
        # Start node in background
        if uv run formix -nn --type "$node_type" &>/dev/null &
        then
            local node_pid=$!
            
            # Wait for node to start
            sleep $NODE_START_DELAY
            
            # Check if process is still running
            if ps -p $node_pid >/dev/null 2>&1; then
                log_success "Started $node_type node #$node_number (PID: $node_pid)"
                sleep $NODE_STABILIZE_DELAY
                return 0
            else
                log_warning "$node_type node #$node_number failed to start (process died)"
            fi
        else
            log_warning "Failed to launch $node_type node #$node_number"
        fi
        
        ((attempt++))
        if [ $attempt -le $MAX_RETRIES ]; then
            log_info "Retrying in 2 seconds..."
            sleep 2
        fi
    done
    
    log_error "Failed to create $node_type node #$node_number after $MAX_RETRIES attempts"
    return 1
}

# Function to verify nodes are running correctly
verify_network() {
    log_info "Verifying network status..."
    sleep $VERIFICATION_DELAY
    
    local view_output
    view_output=$(uv run formix --view 2>/dev/null || echo "ERROR")
    
    if echo "$view_output" | grep -q "No nodes"; then
        log_error "No nodes found in network after setup"
        return 1
    elif echo "$view_output" | grep -q "ERROR\|Failed"; then
        log_error "Error checking network status"
        return 1
    else
        log_success "Network verification successful:"
        echo "$view_output"
        
        # Count nodes
        local heavy_count light_count
        heavy_count=$(echo "$view_output" | grep -c "heavy" || echo "0")
        light_count=$(echo "$view_output" | grep -c "light" || echo "0")
        
        log_info "Network summary: $heavy_count heavy nodes, $light_count light nodes"
        
        if [ "$heavy_count" -eq 3 ] && [ "$light_count" -eq 2 ]; then
            return 0
        else
            log_warning "Expected 3 heavy and 2 light nodes, got $heavy_count heavy and $light_count light"
            return 1
        fi
    fi
}

# Function to show usage information
show_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -v, --verbose  Enable verbose output"
    echo "  -q, --quiet    Suppress non-error output"
    echo ""
    echo "This script creates a 5-node Formix network (3 heavy + 2 light nodes)"
    echo "with proper startup delays and error handling."
}

# Main execution function
main() {
    local verbose=false
    local quiet=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            -q|--quiet)
                quiet=true
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Redirect output based on quiet flag
    if [ "$quiet" = true ]; then
        exec 2>/dev/null
    fi
    
    log_info "Starting Formix 5-node network setup..."
    log_info "Configuration: 3 heavy nodes + 2 light nodes"
    
    # Pre-flight checks
    check_formix_cli
    
    # Cleanup any existing nodes
    cleanup_existing_nodes
    
    # Create heavy nodes
    log_info "Creating heavy nodes..."
    for i in {1..3}; do
        if ! create_node_with_retries "heavy" $i; then
            log_error "Failed to create heavy node $i, aborting setup"
            exit 1
        fi
    done
    
    # Give heavy nodes time to stabilize before adding light nodes
    log_info "Waiting for heavy nodes to stabilize..."
    sleep $HEAVY_LIGHT_DELAY
    
    # Create light nodes
    log_info "Creating light nodes..."
    for i in {1..2}; do
        if ! create_node_with_retries "light" $i; then
            log_error "Failed to create light node $i, aborting setup"
            exit 1
        fi
    done
    
    # Final verification
    if verify_network; then
        log_success "✅ All 5 nodes created successfully!"
        echo ""
        log_info "Next steps:"
        echo "  • View network: uv run formix --view"
        echo "  • Create computation: uv run formix --comp"
        echo "  • Stop all nodes: uv run formix --stop-all"
        exit 0
    else
        log_error "❌ Network verification failed"
        log_info "You may want to run 'uv run formix --stop-all' to clean up"
        exit 1
    fi
}

# Trap to handle script interruption
cleanup_on_interrupt() {
    log_warning "Script interrupted!"
    log_info "To clean up any partially created nodes, run: uv run formix --stop-all"
    exit 130
}

trap cleanup_on_interrupt INT TERM

# Execute main function with all arguments
main "$@"