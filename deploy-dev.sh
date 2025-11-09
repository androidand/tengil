#!/bin/bash
# Development workflow for testing Tengil on remote Proxmox

PROXMOX_HOST="${PROXMOX_HOST:-root@proxmox.local}"
PROXMOX_DIR="/tmp/tengil-dev"

echo "🚀 Deploying to $PROXMOX_HOST..."

# Sync code to Proxmox
rsync -avz --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    ./ "$PROXMOX_HOST:$PROXMOX_DIR/"

# Setup and run on Proxmox
ssh "$PROXMOX_HOST" << 'ENDSSH'
cd /tmp/tengil-dev

# Setup venv if needed
if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install poetry
fi

# Install dependencies
.venv/bin/poetry install

# Run in mock mode by default
export TG_MOCK=1
echo ""
echo "📋 Available commands:"
echo "  .venv/bin/poetry run tg diff"
echo "  .venv/bin/poetry run tg apply --dry-run"
echo ""
echo "🔧 Mock mode is ENABLED (TG_MOCK=1)"
echo ""
ENDSSH

echo ""
echo "✅ Deployed! SSH into Proxmox to test:"
echo "   ssh $PROXMOX_HOST"
echo "   cd $PROXMOX_DIR"
echo "   .venv/bin/poetry run tg diff"
