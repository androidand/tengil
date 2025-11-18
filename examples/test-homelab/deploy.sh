#!/bin/bash
set -e

SERVER="root@192.168.1.42"
CONFIG_FILE="tengil.yml"

# Load environment if available
if [ -f ".env" ]; then
    source .env
    SERVER="root@${PROXMOX_SERVER:-192.168.1.42}"
fi

echo "🚀 Deploying homelab to $SERVER..."

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config file $CONFIG_FILE not found"
    exit 1
fi

# Test connection
echo "📡 Testing connection to Proxmox..."
if ! ssh -o ConnectTimeout=5 "$SERVER" "echo 'Connection OK'"; then
    echo "❌ Cannot connect to $SERVER"
    echo "💡 Make sure SSH keys are set up: ssh-copy-id $SERVER"
    exit 1
fi

# Sync config to server
echo "📁 Syncing configuration..."
rsync -av "$CONFIG_FILE" "$SERVER:/root/"

# Check if tengil is installed on server
echo "🔧 Checking Tengil installation..."
if ! ssh "$SERVER" "which tg >/dev/null 2>&1"; then
    echo "❌ Tengil not installed on server"
    echo "💡 Install with: curl -fsSL https://raw.githubusercontent.com/androidand/tengil/main/scripts/install.sh | sudo bash"
    exit 1
fi

# Preview changes
echo "👀 Previewing changes..."
ssh "$SERVER" "cd /root && tg diff --config $CONFIG_FILE"

# Ask for confirmation unless --yes flag
if [[ "$1" != "--yes" ]]; then
    read -p "🤔 Apply these changes? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deployment cancelled"
        exit 0
    fi
fi

# Apply configuration
echo "⚡ Applying configuration..."
ssh "$SERVER" "cd /root && tg apply --config $CONFIG_FILE --yes"

# Deploy app to container
echo "📦 Deploying Home Assistant MCP Server..."
echo "📁 Syncing app files..."
rsync -av apps/ "$SERVER:/tmp/tengil-apps/"

# Handle environment variables
echo "🔐 Setting up environment variables..."
if [ -f ".env" ]; then
    echo "📝 Found .env file, syncing to container..."
    scp .env "$SERVER:/tmp/app.env"
else
    echo "⚠️  No .env file found, using demo mode"
    scp .env.example "$SERVER:/tmp/app.env"
fi

# Setup app in container
echo "🔧 Setting up app in container..."
ssh "$SERVER" << 'EOF'
# Copy setup script and env to container
pct push hass-mcp /tmp/tengil-apps/hass-mcp/setup.sh /tmp/setup.sh
pct push hass-mcp /tmp/app.env /tmp/app.env

# Make executable and run
pct exec hass-mcp -- chmod +x /tmp/setup.sh
pct exec hass-mcp -- /tmp/setup.sh

# Sync environment using Tengil's built-in env management
tg env sync hass-mcp /tmp/app.env --restart hass-mcp

# Check if service is running
echo "🔍 Checking service status..."
pct exec hass-mcp -- systemctl status hass-mcp --no-pager
EOF

echo "✅ Deployment complete!"
echo "🌐 Home Assistant MCP Server: http://192.168.1.42:3000"
echo "📁 SMB share: \\\\192.168.1.42\\HomeAssistant"
echo "🐳 Container shell: ssh $SERVER 'pct enter hass-mcp'"
echo "📊 Service status: ssh $SERVER 'pct exec hass-mcp -- systemctl status hass-mcp'"