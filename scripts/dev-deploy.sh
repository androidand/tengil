#!/bin/bash
# Development workflow for testing Tengil on remote Proxmox
# Usage: ./scripts/dev-deploy.sh [user@host]
# Example: ./scripts/dev-deploy.sh root@192.168.1.100
# Or set PROXMOX_HOST env: export PROXMOX_HOST=root@proxmox.local

set -e

PROXMOX_HOST="${1:-${PROXMOX_HOST:-root@proxmox.local}}"
PROXMOX_DIR="/tmp/tengil-dev"

# Check dependencies
if ! command -v rsync &> /dev/null; then
    echo "❌ rsync is required. Install with:"
    echo "   macOS: brew install rsync"
    echo "   Linux: apt install rsync"
    exit 1
fi

echo "🚀 Deploying to $PROXMOX_HOST..."

# Test SSH connection
if ! ssh -o ConnectTimeout=5 "$PROXMOX_HOST" "echo ''" &>/dev/null; then
    echo "❌ Cannot connect to $PROXMOX_HOST"
    echo ""
    echo "💡 Setup SSH keys first:"
    echo "   ssh-copy-id $PROXMOX_HOST"
    exit 1
fi

# Sync code to Proxmox
echo "📦 Syncing code..."
rsync -avz --delete \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.coverage' \
    --exclude='.local' \
    ./ "$PROXMOX_HOST:$PROXMOX_DIR/"

# Setup and run on Proxmox
echo "🔧 Setting up environment on Proxmox..."
ssh "$PROXMOX_HOST" << 'ENDSSH'
cd /tmp/tengil-dev

# Setup venv if needed
if [ ! -d .venv ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q poetry
fi

# Install dependencies
echo "Installing dependencies..."
.venv/bin/poetry install -q

# Run in mock mode by default
export TG_MOCK=1
echo ""
echo "✅ Tengil deployed successfully!"
echo ""
echo "📋 Try these commands:"
echo "  .venv/bin/poetry run tg diff"
echo "  .venv/bin/poetry run tg apply --dry-run"
echo "  .venv/bin/poetry run tg packages list"
echo "  .venv/bin/poetry run tg doctor"
echo ""
echo "🔧 Mock mode is ENABLED (TG_MOCK=1)"
echo "   Set TG_MOCK=0 for real operations"
echo ""
ENDSSH

echo ""
echo "✅ Development environment ready!"
echo ""
echo "🎯 Next steps:"
echo "   ssh $PROXMOX_HOST"
echo "   cd $PROXMOX_DIR"
echo "   .venv/bin/poetry run tg diff"
echo ""
echo "💡 Tip: Add this to your shell profile for quick access:"
echo "   alias tg-dev='./scripts/dev-deploy.sh'"
