#!/bin/bash
set -e

# Tengil Unified Installer
# 
# Usage from Mac/workstation:
#   ./scripts/install.sh root@proxmox-ip              # Remote install from GitHub
#   ./scripts/install.sh root@proxmox-ip --local      # Remote install from local repo
#
# Usage on Proxmox directly:
#   ./scripts/install.sh                              # Local install from GitHub
#   ./scripts/install.sh --local                      # Local install from current directory
#   ./scripts/install.sh --dev                        # Quick dev mode (/tmp, mock enabled)

# Parse arguments
REMOTE_HOST=""
MODE="github"

# Check if first arg is a host (contains @)
if [[ "$1" =~ @ ]]; then
    REMOTE_HOST="$1"
    shift
fi

# Check for mode flag
if [[ "$1" == "--local" ]]; then
    MODE="local"
elif [[ "$1" == "--dev" ]]; then
    MODE="dev"
fi

# If remote host specified, SSH and run the script there
if [[ -n "$REMOTE_HOST" ]]; then
    echo "🚀 Installing Tengil on remote host: $REMOTE_HOST"
    echo ""
    
    # Check SSH connectivity
    if ! ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo ''" &>/dev/null; then
        echo "❌ Cannot connect to $REMOTE_HOST"
        echo ""
        echo "💡 Setup SSH keys first:"
        echo "   ssh-copy-id $REMOTE_HOST"
        exit 1
    fi
    
    # Get script directory
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
    
    if [[ "$MODE" == "local" ]]; then
        # Sync local repo and run install
        echo "📦 Syncing local repository to remote host..."
        TEMP_DIR="/tmp/tengil-install-$$"
        ssh "$REMOTE_HOST" "mkdir -p $TEMP_DIR"
        
        rsync -az --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
            --exclude='.pytest_cache' --exclude='.coverage' --exclude='.local' \
            "$REPO_ROOT/" "$REMOTE_HOST:$TEMP_DIR/"
        
        echo "🔧 Running installer on remote host..."
        ssh -t "$REMOTE_HOST" "cd $TEMP_DIR && ./scripts/install.sh --local && rm -rf $TEMP_DIR"
    else
        # Just download and run install script from GitHub
        echo "📥 Installing from GitHub on remote host..."
        ssh -t "$REMOTE_HOST" "curl -fsSL https://raw.githubusercontent.com/androidand/tengil/main/scripts/install.sh | bash"
    fi
    
    echo ""
    echo "✅ Remote installation complete!"
    echo ""
    echo "Connect to your Proxmox server:"
    echo "   ssh $REMOTE_HOST"
    echo "   source ~/.bashrc"
    echo "   tg packages list"
    exit 0
fi

# From here on, we're running ON the target machine

echo "╔════════════════════════════════════════╗"
echo "║  Tengil - Proxmox ZFS Orchestration   ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "Mode: $MODE"
echo ""

# Check if running on Proxmox (skip for dev mode)
if [[ "$MODE" != "dev" ]] && [ ! -f /etc/pve/.version ]; then
    echo "⚠️  Warning: This doesn't appear to be a Proxmox VE system"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check for root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Please run as root (sudo)"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip git

# Determine installation directory
if [[ "$MODE" == "dev" ]]; then
    INSTALL_DIR="/tmp/tengil-dev"
    echo "📂 Dev mode: Installing to $INSTALL_DIR (temporary)"
else
    INSTALL_DIR="/opt/tengil"
    echo "📂 Installing to $INSTALL_DIR..."
fi

# Clone, copy, or update
if [[ "$MODE" == "github" ]]; then
    if [ -d "$INSTALL_DIR" ]; then
        echo "♻️  Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull
    else
        echo "📥 Cloning from GitHub..."
        git clone https://github.com/androidand/tengil.git "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
elif [[ "$MODE" == "local" ]]; then
    echo "📦 Copying from current directory..."
    # Get the repo root (script is in scripts/)
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
    
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        --exclude='.pytest_cache' --exclude='.coverage' --exclude='.local' \
        "$REPO_ROOT/" "$INSTALL_DIR/"
    cd "$INSTALL_DIR"
elif [[ "$MODE" == "dev" ]]; then
    echo "📦 Copying from current directory (dev mode)..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(dirname "$SCRIPT_DIR")"
    
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        --exclude='.pytest_cache' --exclude='.coverage' --exclude='.local' \
        "$REPO_ROOT/" "$INSTALL_DIR/"
    cd "$INSTALL_DIR"
fi

# Setup virtual environment
echo "🐍 Setting up Python environment..."
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q poetry
.venv/bin/poetry install

# Setup shell alias
if [[ "$MODE" == "dev" ]]; then
    echo "🔧 Dev mode: Mock mode enabled (TG_MOCK=1)"
    export TG_MOCK=1
else
    echo "🔗 Creating shell alias..."
    ALIAS_LINE="alias tg=\"cd $INSTALL_DIR && .venv/bin/poetry run tg\""
    if ! grep -q "alias tg=" ~/.bashrc 2>/dev/null; then
        echo "$ALIAS_LINE" >> ~/.bashrc
        echo "✓ Added 'tg' alias to ~/.bashrc"
    else
        echo "✓ Alias already exists in ~/.bashrc"
    fi
fi

# Setup working directory (not for dev mode)
if [[ "$MODE" != "dev" ]]; then
    echo "⚙️  Creating working directory..."
    mkdir -p ~/tengil-configs
    if [ ! -f ~/tengil-configs/tengil.yml ]; then
        echo "version: 2" > ~/tengil-configs/tengil.yml
        echo "pools: {}" >> ~/tengil-configs/tengil.yml
        echo "📝 Created ~/tengil-configs/tengil.yml"
    else
        echo "✓ Config already exists at ~/tengil-configs/tengil.yml"
    fi
fi

echo ""
echo "✅ Installation complete!"
echo ""

if [[ "$MODE" == "dev" ]]; then
    echo "Dev mode quick test:"
    echo "  cd $INSTALL_DIR"
    echo "  export TG_MOCK=1"
    echo "  .venv/bin/poetry run tg packages list"
    echo "  .venv/bin/poetry run tg diff"
    echo ""
    echo "Note: Installed to /tmp - will be deleted on reboot"
else
    echo "Reload your shell: source ~/.bashrc"
    echo ""
    echo "Quick start:"
    echo "  cd ~/tengil-configs"
    echo "  tg packages list           # Browse 13 preset packages"
    echo "  tg init --package nas-basic # Create config from preset"
    echo "  tg diff                     # Preview changes"
    echo "  tg apply --dry-run          # Test run"
    echo "  tg apply                    # Execute"
fi
echo ""
