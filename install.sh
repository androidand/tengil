#!/bin/bash
set -e

echo "╔════════════════════════════════════════╗"
echo "║  Tengil - Proxmox ZFS Orchestration   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if running on Proxmox
if [ ! -f /etc/pve/.version ]; then
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

# Choose installation directory
INSTALL_DIR="/opt/tengil"
echo "📂 Installing to $INSTALL_DIR..."

# Clone or update
if [ -d "$INSTALL_DIR" ]; then
    echo "♻️  Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "📥 Cloning repository..."
    git clone https://github.com/androidand/tengil.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Setup virtual environment
echo "🐍 Setting up Python environment..."
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q poetry
.venv/bin/poetry install

# Create symlink
echo "🔗 Creating command link..."
ln -sf "$INSTALL_DIR/.venv/bin/tg" /usr/local/bin/tg

# Setup config directory
echo "⚙️  Setting up configuration..."
mkdir -p /etc/tengil
if [ ! -f /etc/tengil/tengil.yml ]; then
    cp examples/tengil.yml.example /etc/tengil/tengil.yml
    echo "📝 Created /etc/tengil/tengil.yml - edit this file"
else
    echo "✓ Configuration already exists at /etc/tengil/tengil.yml"
fi

# Create state directory
mkdir -p /var/lib/tengil

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Edit /etc/tengil/tengil.yml"
echo "  2. Run: tg diff"
echo "  3. Run: tg apply --dry-run"
echo "  4. Run: tg apply (when ready)"
echo ""
echo "Test with mock mode first:"
echo "  export TG_MOCK=1"
echo "  tg diff"
echo ""
