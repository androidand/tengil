# Deploying Home Assistant MCP Server with Tengil

This guide shows how to deploy the Home Assistant MCP server to Proxmox using Tengil.

## What is HA MCP?

The Home Assistant MCP (Model Context Protocol) server enables AI assistants like Claude to:
- Create and edit automations
- Control devices
- Monitor real-time state changes
- Manage Supervisor and add-ons
- Integrate with HACS

**Repository**: https://github.com/tevonsb/homeassistant-mcp

## Prerequisites

- Proxmox VE with Tengil installed
- Home Assistant instance running on your network
- ZFS pool (e.g., `tank`)

## Deployment Steps

### 1. Initialize HA MCP Configuration

```bash
cd ~/tengil-configs
tg init --package ha-mcp
```

This creates `tengil.yml` with the MCP server configuration.

### 2. Review Configuration (Optional)

```bash
cat tengil.yml
```

The generated config includes:
- LXC container (`mcp-server`) with Ubuntu 24.04
- 2GB RAM, 2 cores, 16GB disk
- Privileged mode with nesting/fuse/keyctl features
- Automated Node.js 20 installation
- Automated MCP server setup

### 3. Preview Deployment

```bash
tg diff
```

This shows what Tengil will create without making changes.

### 4. Deploy

```bash
tg apply
```

Tengil will:
1. Download Ubuntu 24.04 template (if needed)
2. Create privileged LXC container
3. Install Node.js 20
4. Clone and build MCP server
5. Set up systemd service
6. Create update script

**Time**: 5-10 minutes depending on network speed.

### 5. Configure Home Assistant Credentials

After deployment, you need to configure the MCP server with your Home Assistant details:

#### Get Long-Lived Access Token

1. Open Home Assistant web UI
2. Click your profile (bottom left)
3. Scroll to "Long-Lived Access Tokens"
4. Click "Create Token"
5. Name it "MCP Server"
6. Copy the token (you won't see it again!)

#### Edit Configuration

```bash
# Edit the .env file
tg container exec mcp-server -- nano /opt/homeassistant-mcp/.env
```

Update these values:
```env
HASS_HOST=http://homeassistant.local:8123  # Your HA URL
HASS_TOKEN=eyJ0eXAiOiJKV1QiLCJh...          # Your long-lived token
HASS_SOCKET_URL=ws://homeassistant.local:8123/api/websocket
```

Save and exit (Ctrl+X, then Y, then Enter).

### 6. Start the MCP Server

```bash
# Start the service
tg container exec mcp-server -- systemctl start mcp-server

# Check status
tg container exec mcp-server -- systemctl status mcp-server

# View logs
tg container exec mcp-server -- journalctl -u mcp-server -f
```

### 7. Test the Server

```bash
# Get container IP
tg container exec mcp-server -- hostname -I

# Test health endpoint (from your Mac)
curl http://<container-ip>:3000/health
```

You should get a JSON response indicating the server is healthy.

### 8. Connect to Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "HomeAssistant": {
      "command": "mcp-proxy",
      "args": [
        "--transport=streamablehttp",
        "--stateless",
        "http://<container-ip>:3000"
      ]
    }
  }
}
```

Replace `<container-ip>` with your container's IP address.

Restart Claude Desktop and check the MCP server list - it should show as GREEN.

## Management Commands

### View Logs
```bash
tg container exec mcp-server -- journalctl -u mcp-server -f
```

### Restart Service
```bash
tg container exec mcp-server -- systemctl restart mcp-server
```

### Update MCP Server
```bash
tg container exec mcp-server -- /opt/homeassistant-mcp/update.sh
```

### Shell Access
```bash
tg container shell mcp-server
```

### Stop/Start Container
```bash
tg container stop mcp-server
tg container start mcp-server
```

## Comparison: Manual vs Tengil

### Manual Process (ha-mcp.md)
- **Time**: 30-45 minutes
- **Steps**: 10+ manual steps
- **Complexity**: High (systemd, Node.js, git, npm)
- **Reproducibility**: Low (manual steps)
- **Documentation**: Must maintain separately

### Tengil Automated
- **Time**: 5-10 minutes (mostly waiting)
- **Steps**: 3 commands + config edit
- **Complexity**: Low (declarative YAML)
- **Reproducibility**: High (version-controlled config)
- **Documentation**: Built-in (package includes notes)

## Troubleshooting

### MCP Server Won't Start

```bash
# Check logs
tg container exec mcp-server -- journalctl -u mcp-server -n 50

# Common issues:
# - Wrong Home Assistant URL
# - Invalid access token
# - Home Assistant not reachable from container
```

### Node.js Version Issues

```bash
# Check Node.js version
tg container exec mcp-server -- node -v
# Should show v20.x.x

# Reinstall if needed
tg container exec mcp-server -- apt-get update && apt-get install -y nodejs
```

### Network Connectivity

```bash
# Test HA connectivity from container
tg container exec mcp-server -- curl http://homeassistant.local:8123
```

## Advanced: Custom Configuration

### Change Port

Edit `tengil.yml` before deploying:

```yaml
containers:
  - name: mcp-server
    network:
      ip: "192.168.1.50/24"  # Static IP
    # ... rest of config
```

### Add Persistent Storage

To preserve config across container rebuilds:

```yaml
pools:
  tank:
    datasets:
      mcp-config:
        profile: appdata
        containers:
          - name: mcp-server
            mount: /opt/homeassistant-mcp/config
            readonly: false
```

## Backup & Recovery

### Take Snapshot

```bash
# From Proxmox web UI:
# Container → Snapshots → Take Snapshot
# Name: "working-mcp-server"

# Or via CLI:
tg snapshot --name working-mcp-server
```

### Restore from Snapshot

```bash
tg rollback mcp-server --to working-mcp-server
```

### Git-Based Backup

```bash
cd ~/tengil-configs
git add tengil.yml
git commit -m "Add HA MCP server config"
git push
```

Now you can restore on any Proxmox host:

```bash
git clone <your-repo>
cd tengil-configs
tg apply
```

## Next Steps

- Explore MCP features in Claude Desktop
- Set up automation triggers
- Monitor Home Assistant state changes
- Create custom automations via Claude

## Resources

- [HA MCP Repository](https://github.com/tevonsb/homeassistant-mcp)
- [Tengil Documentation](../docs/USER_GUIDE.md)
- [Home Assistant](https://www.home-assistant.io/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
