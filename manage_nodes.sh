#!/bin/bash

# Simple node management utility for Formix
# Usage: ./manage_nodes.sh [start|stop|status|restart|clean]

set -euo pipefail

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_formix() {
    if ! command -v uv >/dev/null 2>&1; then
        log_error "uv not found. Please install uv first."
        exit 1
    fi
    
    if ! uv run formix --help >/dev/null 2>&1; then
        log_error "formix CLI not working. Check your installation."
        exit 1
    fi
}

start_nodes() {
    log_info "Starting 5-node Formix network..."
    if [ -f "./run_nodes_robust.sh" ]; then
        ./run_nodes_robust.sh
    else
        log_error "No node startup script found!"
        exit 1
    fi
}

stop_nodes() {
    log_info "Stopping all Formix nodes..."
    printf "y\n" | uv run formix --stop-all 2>/dev/null || {
        log_warning "No nodes to stop or stop command failed"
    }
    log_success "Stop command completed"
}

show_status() {
    log_info "Current network status:"
    uv run formix --view 2>/dev/null || {
        log_warning "Unable to get network status"
    }
}

restart_nodes() {
    log_info "Restarting Formix network..."
    stop_nodes
    sleep 3
    start_nodes
}

clean_environment() {
    log_info "Cleaning Formix environment..."
    stop_nodes
    
    # Clean up any leftover processes
    pkill -f "formix" 2>/dev/null || log_info "No formix processes to kill"
    
    # Clean up database if needed (be careful with this)
    if [ -d "$HOME/.formix" ]; then
        log_warning "Formix data directory exists at $HOME/.formix"
        read -p "Do you want to remove it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$HOME/.formix"
            log_success "Cleaned up Formix data directory"
        fi
    fi
    
    log_success "Environment cleanup completed"
}

show_help() {
    echo "Formix Node Management Utility"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  start    - Start the 5-node network (3 heavy + 2 light)"
    echo "  stop     - Stop all running nodes"
    echo "  status   - Show current network status"
    echo "  restart  - Stop all nodes and start fresh network"
    echo "  clean    - Stop nodes and clean up environment"
    echo "  help     - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start    # Start the network"
    echo "  $0 status   # Check what's running"
    echo "  $0 stop     # Stop everything"
}

main() {
    local command=${1:-help}
    
    case $command in
        start)
            check_formix
            start_nodes
            ;;
        stop)
            check_formix
            stop_nodes
            ;;
        status)
            check_formix
            show_status
            ;;
        restart)
            check_formix
            restart_nodes
            ;;
        clean)
            check_formix
            clean_environment
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

main "$@"