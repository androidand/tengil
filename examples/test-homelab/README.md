# Test Homelab - Home Assistant MCP Server

This is a test deployment of a real-world application using Tengil to manage Proxmox infrastructure.

## What This Deploys

- **Home Assistant MCP Server**: A Node.js/Bun application that provides LLM integration with Home Assistant
- **ZFS Storage**: Optimized datasets with smart permissions
- **LXC Container**: Debian 12 container with auto-creation
- **SMB Shares**: Network accessible storage
- **Systemd Service**: Proper service management

## Quick Start

1. **Configure your environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your Proxmox server IP and Home Assistant details
   ```

2. **Deploy to Proxmox**:
   ```bash
   ./deploy.sh
   ```

3. **Access the application**:
   - Web interface: http://192.168.1.42:3000
   - SMB share: \\192.168.1.42\HomeAssistant
   - Container shell: `ssh root@192.168.1.42 'pct enter hass-mcp'`

## What Tengil Does

### Infrastructure (tengil.yml)
- Creates ZFS dataset `tank/homeassistant` with `appdata` profile
- Provisions LXC container `hass-mcp` with 2GB RAM, 2 cores
- Sets up SMB share with readwrite permissions (auto-inferred)
- Configures proper mount points and networking

### Smart Defaults Applied
- **Profile**: `appdata` → readwrite access for app data
- **Container**: Auto-detected as Node.js app → readwrite permissions
- **SMB Share**: Inherits readwrite from container permissions
- **ZFS Settings**: Optimized for application data (compression, recordsize)

### Application Deployment
- Clones Home Assistant MCP Server from GitHub
- Installs Node.js, Bun, and dependencies
- Creates systemd service for proper lifecycle management
- Sets up environment configuration
- Starts in demo mode (HASS_MOCK=true)

## Environment Variable Management

Tengil provides secure environment variable management for your applications:

### Quick Setup
1. **Edit local environment**:
   ```bash
   cp .env.example .env
   nano .env  # Add your Home Assistant URL and token
   ```

2. **Deploy with environment**:
   ```bash
   ./deploy.sh  # Automatically syncs .env to container
   ```

### Managing Secrets

**Using Tengil's built-in commands** (recommended):
```bash
tg env list hass-mcp              # List environment variables
tg env set hass-mcp HASS_MOCK false --restart hass-mcp
tg env sync hass-mcp .env --restart hass-mcp
```

**Using helper scripts**:
```bash
./scripts/manage-env.sh list      # List env vars
./scripts/manage-env.sh set VAR value  # Set single variable
./scripts/manage-env.sh sync      # Push local .env to container
./scripts/manage-env.sh logs      # Real-time logs
./scripts/manage-env.sh status    # Service status
```

### Home Assistant Integration
To connect to a real Home Assistant instance:

1. Get a long-lived access token from Home Assistant
2. Edit your local `.env` file:
   ```bash
   nano .env
   ```
3. Set your Home Assistant URL and token:
   ```
   HASS_URL=http://your-homeassistant:8123
   HASS_TOKEN=your_actual_token_here
   HASS_MOCK=false
   ```
4. Sync to container:
   ```bash
   ./scripts/manage-env.sh sync
   ```

### Service Management
```bash
# Using the management script (recommended)
./scripts/manage-env.sh status   # Check status
./scripts/manage-env.sh logs     # View logs
./scripts/manage-env.sh restart  # Restart service

# Or directly via SSH
ssh root@192.168.1.42 'pct exec hass-mcp -- systemctl status hass-mcp'
```

## File Structure

```
test-homelab/
├── tengil.yml          # Infrastructure configuration
├── deploy.sh           # Deployment script
├── .env                # Environment variables (secrets)
├── .env.example        # Environment template
├── .gitignore          # Security exclusions
├── README.md           # This file
├── scripts/
│   └── manage-env.sh   # Environment management
└── apps/
    └── hass-mcp/
        └── setup.sh    # Application setup script
```

## Testing the Deployment

1. **Verify infrastructure**:
   ```bash
   ssh root@192.168.1.42 'tg diff'  # Should show "up to date"
   ```

2. **Check container**:
   ```bash
   ssh root@192.168.1.42 'pct list | grep hass-mcp'
   ```

3. **Test application**:
   ```bash
   curl http://192.168.1.42:3000/health  # Should return app status
   ```

4. **Access SMB share**:
   - macOS: `cmd+k` → `smb://192.168.1.42/HomeAssistant`
   - Windows: `\\192.168.1.42\HomeAssistant`

## Next Steps

This demonstrates the complete Tengil workflow:
- ✅ Infrastructure as Code (tengil.yml)
- ✅ Smart permission defaults
- ✅ Real application deployment
- ✅ Git-based configuration management
- ✅ Mac → Proxmox deployment pipeline

For production use, consider:
- Setting up proper Home Assistant integration
- Configuring SSL/TLS certificates
- Adding monitoring and backups
- Using secrets management for tokens