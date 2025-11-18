#!/bin/bash
set -e

echo "🏠 Setting up Home Assistant MCP Server..."

# Update system
apt update && apt upgrade -y

# Install Node.js and Bun
echo "📦 Installing Node.js and Bun..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs git

# Install Bun
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"
echo 'export PATH="$HOME/.bun/bin:$PATH"' >> ~/.bashrc

# Clone and setup the MCP server
echo "📥 Cloning Home Assistant MCP Server..."
cd /app
git clone https://github.com/oleander/home-assistant-mcp-server.git .

# Install dependencies
echo "📦 Installing dependencies..."
bun install
bun run build

# Create systemd service
echo "🔧 Creating systemd service..."
cat > /etc/systemd/system/hass-mcp.service << 'EOF'
[Unit]
Description=Home Assistant MCP Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/app
Environment=NODE_ENV=production
EnvironmentFile=/app/.env
ExecStart=/root/.bun/bin/bun run start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create environment template
echo "📝 Creating environment template..."
cat > /app/.env.example << 'EOF'
# Home Assistant Configuration
HASS_URL=http://your-home-assistant:8123
HASS_TOKEN=your_long_lived_access_token

# Server Configuration
PORT=3000

# Demo mode (set to true for testing without Home Assistant)
HASS_MOCK=true
EOF

# Copy to actual .env for demo mode
cp /app/.env.example /app/.env

# Enable and start service
systemctl daemon-reload
systemctl enable hass-mcp
systemctl start hass-mcp

echo "✅ Home Assistant MCP Server setup complete!"
echo "🌐 Server running on port 3000 (demo mode)"
echo "📝 Edit /app/.env to configure your Home Assistant connection"
echo "🔧 Manage with: systemctl status/restart hass-mcp"