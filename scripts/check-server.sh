#!/bin/bash
# Check Tengil server status and health
# Usage: ./scripts/check-server.sh [command]
#
# Commands:
#   status    - Show Tengil installation status (default)
#   config    - Show current config file
#   version   - Show Tengil version
#   pools     - Show ZFS pools
#   packages  - List available packages
#   logs      - Show recent activity
#   all       - Run all checks

set -e

# Configuration
SERVER="${TENGIL_SERVER:-root@192.168.1.42}"
TENGIL_DIR="/opt/tengil"
CONFIG_DIR="~/tengil-configs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Helper functions
header() {
    echo -e "\n${CYAN}=== $1 ===${NC}"
}

success() {
    echo -e "${GREEN}✓${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Check commands
check_status() {
    header "Tengil Installation Status"
    
    # Check if Tengil is installed
    if ssh "$SERVER" "test -d $TENGIL_DIR" 2>/dev/null; then
        success "Tengil installed at $TENGIL_DIR"
    else
        error "Tengil not found at $TENGIL_DIR"
        return 1
    fi
    
    # Check Python environment
    if ssh "$SERVER" "test -d $TENGIL_DIR/.venv" 2>/dev/null; then
        success "Python venv exists"
    else
        error "Python venv missing"
    fi
    
    # Check alias
    if ssh "$SERVER" "grep -q 'alias tg=' ~/.bashrc" 2>/dev/null; then
        success "tg alias configured"
    else
        error "tg alias not found"
    fi
    
    # Check config directory
    if ssh "$SERVER" "test -d $CONFIG_DIR" 2>/dev/null; then
        success "Config directory exists"
        if ssh "$SERVER" "test -f $CONFIG_DIR/tengil.yml" 2>/dev/null; then
            success "Config file exists"
        else
            info "No config file yet (run 'tg init')"
        fi
    else
        error "Config directory missing"
    fi
}

check_version() {
    header "Tengil Version"
    ssh "$SERVER" "cd $TENGIL_DIR && .venv/bin/poetry run tg version" 2>/dev/null || error "Failed to get version"
}

check_config() {
    header "Current Config"
    if ssh "$SERVER" "test -f $CONFIG_DIR/tengil.yml" 2>/dev/null; then
        ssh "$SERVER" "cat $CONFIG_DIR/tengil.yml"
    else
        info "No config file found"
        info "Run: tg init --package <package-name>"
    fi
}

check_pools() {
    header "ZFS Pools"
    ssh "$SERVER" "zpool list 2>/dev/null" || error "Failed to list pools"
}

check_packages() {
    header "Available Packages"
    ssh "$SERVER" "cd $TENGIL_DIR && .venv/bin/poetry run tg packages list" 2>/dev/null || error "Failed to list packages"
}

check_logs() {
    header "Recent Activity"
    info "Last 20 commands from bash history:"
    ssh "$SERVER" "tail -20 ~/.bash_history | grep -E '(tg|zfs|zpool)' || echo 'No relevant commands found'"
}

check_deployment() {
    header "Last Deployment"
    if ssh "$SERVER" "test -f $TENGIL_DIR/.deployed" 2>/dev/null; then
        ssh "$SERVER" "cat $TENGIL_DIR/.deployed"
    else
        info "No deployment timestamp found"
    fi
}

# Main
COMMAND="${1:-status}"

case "$COMMAND" in
    status)
        check_status
        ;;
    version)
        check_version
        ;;
    config)
        check_config
        ;;
    pools)
        check_pools
        ;;
    packages)
        check_packages
        ;;
    logs)
        check_logs
        ;;
    all)
        check_status
        check_version
        check_pools
        check_config
        check_packages
        ;;
    *)
        echo "Usage: $0 [status|version|config|pools|packages|logs|all]"
        exit 1
        ;;
esac
