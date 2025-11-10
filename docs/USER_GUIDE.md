# Tengil User Guide

Complete reference for using Tengil to manage Proxmox infrastructure.

## Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/androidand/tengil.git
cd tengil
poetry install

# Create alias for convenience
echo 'alias tg="poetry run python -m tengil.cli"' >> ~/.zshrc
source ~/.zshrc

# Verify installation
tg --version
```

### First Deploy - NAS Shares

```bash
# Browse available packages
tg packages list

# Initialize from package (interactive)
tg init --package nas-basic
# Prompts for: pool name, include photos?, backups?, time machine?

# Preview what will be created
tg diff

# Apply to Proxmox
tg apply
```

**Result**: ZFS datasets with SMB shares accessible from your Mac/PC.

### Accessing Shares from Mac

1. **Create SMB user on Proxmox** (SSH to your server):
   ```bash
   # Create system user
   sudo useradd -M -s /sbin/nologin nasuser
   
   # Set Samba password
   sudo smbpasswd -a nasuser
   # Enter password when prompted
   
   # Enable user
   sudo smbpasswd -e nasuser
   ```

2. **Mount from Mac Finder**:
   - Press `Cmd+K` (Go → Connect to Server)
   - Enter: `smb://your-proxmox-ip/Files`
   - Username: `nasuser`, Password: (from step 1)

3. **Mount from Mac Terminal** (persistent):
   ```bash
   # Create mount point
   mkdir -p ~/NAS/Files
   
   # Mount share
   mount_smbfs //nasuser@proxmox-ip/Files ~/NAS/Files
   ```

### Next Steps

```bash
# Add media server
tg add jellyfin

# Review changes
tg diff

# Apply
tg apply

# Access Jellyfin at http://proxmox-ip:8096
```

## Configuration

### Single Pool Setup

```yaml
version: 2
pools:
  tank:
    type: zfs
    datasets:
      media:
        profile: media
        containers:
          - name: jellyfin
            mount: /media
        shares:
          smb:
            name: Media
            browseable: yes
```

### Multi-Pool Setup

```yaml
version: 2
pools:
  rpool:
    type: zfs
    datasets:
      appdata:
        profile: dev
      databases:
        profile: dev
  
  tank:
    type: zfs
    datasets:
      media:
        profile: media
      downloads:
        profile: downloads
```

## Using rpool (OS Pool) Safely

Proxmox reserves these paths on rpool:
- `rpool/ROOT` - OS (don't touch)
- `rpool/data` - VMs (don't touch)
- `rpool/var-lib-vz` - Templates (don't touch)

**Recommended**: Use `rpool/tengil/*` namespace for your datasets.

## Built-in Profiles

- **dev** - App configs, small files (8K recordsize)
- **media** - Movies, photos (1M recordsize)
- **downloads** - Torrents, mixed files (128K recordsize)
- **backups** - Compressed backups (zstd compression)

## Common Tasks

### Adding a Container Mount

```yaml
datasets:
  media:
    containers:
      - name: jellyfin    # Container hostname (not VMID)
        mount: /media      # Path inside container
        readonly: false    # Optional
```

Find container hostnames: `pct config <VMID> | grep hostname`

### Adding SMB Share

```yaml
datasets:
  media:
    shares:
      smb:
        name: Media        # Share name (path auto-calculated)
        browseable: yes
        guest_ok: false    # Require authentication
```

### Adding NFS Export

```yaml
datasets:
  media:
    shares:
      nfs:
        allowed: "192.168.1.0/24"
        options: "rw,sync,no_root_squash"
```

## Naming Rules

**ZFS Pool Names**:
- Valid: `tank`, `rpool`, `nvme-pool`, `data_backup`
- Invalid: `-tank`, `c0`, `mirror`, `raidz`

**ZFS Dataset Names**:
- Valid: `media`, `media/movies`, `app_data`
- Invalid: `../media`, `.hidden`, names with spaces

**Proxmox Storage IDs**:
- Valid: `tank-media`, `nvme_appdata`
- Invalid: names with spaces, >100 chars

## Container Management

### Auto-Creating Containers

Tengil can automatically create LXC containers with `auto_create`:

```yaml
datasets:
  media:
    containers:
      - name: jellyfin
        auto_create: true
        template: debian-12-standard  # Downloaded automatically
        mount: /media
        cores: 2
        memory: 2048
        disk_size: 8
```

### Post-Install Automation

Run tasks after container creation:

```yaml
datasets:
  media:
    containers:
      - name: jellyfin
        auto_create: true
        template: debian-12-standard
        mount: /media
        post_install: tteck/jellyfin  # Use tteck community script
```

**Available post-install options**:

1. **Single-purpose app containers** with tteck scripts (recommended):
   ```yaml
   post_install: tteck/jellyfin      # Dedicated Jellyfin container
   post_install: tteck/homeassistant # Dedicated Home Assistant container
   post_install: tteck/pihole        # Dedicated Pi-hole container
   ```
   **This is the Proxmox way** - each app in its own LXC container. Lightweight, isolated, no Docker needed.

2. **Docker (if you really need it)**:
   ```yaml
   post_install: [docker, portainer]
   ```
   Only use if you have existing Docker Compose stacks or need Docker-specific images.
   Most apps have tteck scripts - use those instead (lighter, faster, native LXC).

3. **System setup** with custom commands:
   ```yaml
   post_install: |
     apt-get update && apt-get install -y curl git vim
     echo "Europe/Stockholm" > /etc/timezone
     dpkg-reconfigure -f noninteractive tzdata
   ```
   Use for base system configuration (packages, timezone, SSH keys, etc.)

**Which approach to use?**

- **Proxmox native (recommended)**: Use tteck scripts - one LXC per app. This IS the container solution.
- **Docker refugee**: If migrating from Docker Compose, use Docker + Portainer temporarily, then migrate to native LXC.
- **Hybrid**: Mix both - critical services in dedicated LXC, experimental stuff in Docker.

**Why LXC over Docker?**
- **Lighter** - No Docker daemon overhead
- **Faster** - Direct kernel access
- **Simpler** - Standard Linux tools (systemctl, apt, etc.)
- **Isolated** - Each app in its own container with its own ZFS dataset

**Popular tteck scripts**: jellyfin, plex, immich, homeassistant, pihole, nextcloud, sonarr, radarr  
**Full list**: https://tteck.github.io/Proxmox/

**Note**: Post-install is experimental. Test in dev environment first.

## Troubleshooting

### "Dataset already exists"
Tengil detects existing datasets and won't recreate them. Use `tg import` to generate config from existing setup.

### "Container not found" with manual containers
If you created containers manually in Proxmox, Tengil can mount datasets into them. Just specify the container name in your config.

### "Container not found" with auto_create
Template name might be incorrect or not available. 

**LXC templates** are the base OS (Debian, Ubuntu, etc.):
```bash
tg templates              # List all available LXC OS templates
tg templates --local      # Show downloaded templates
```

Common LXC templates: `debian-12-standard`, `ubuntu-22.04-standard`, `debian-11-standard`

**Apps** are installed after via `post_install` (Jellyfin, Plex, etc.):
```yaml
post_install: tteck/jellyfin      # Install Jellyfin app
post_install: tteck/homeassistant # Install Home Assistant
post_install: [docker, portainer] # Install Docker + Portainer
```

See tteck scripts for 200+ apps: https://tteck.github.io/Proxmox/

### Cross-pool hardlinks warning
*arr apps (Sonarr, Radarr) need media on same pool for hardlinks. Don't split downloads and media across pools.

## Docker Compose Integration

Tengil can use upstream Docker Compose files as the source of truth for application infrastructure requirements, then add ZFS storage optimization on top.

### Why Compose Integration?

**The Problem**: Maintaining package definitions for every app means tracking upstream changes constantly.

**The Solution**: Let app developers maintain their compose files. Tengil adds:
- ZFS storage optimization (profiles, recordsize, compression)
- Permission management (consumers model)
- Share configuration (SMB/NFS)
- Container resource allocation

### How It Works

```
docker-compose.yml (upstream)
        ↓
  ComposeAnalyzer (extracts volumes, secrets, ports)
        ↓
  OpinionMerger (adds Tengil storage hints)
        ↓
    tengil.yml (generated config)
```

### Example: ROM Manager Package

```yaml
# tengil/packages/rom-manager-compose.yml
docker_compose:
  source: "https://raw.githubusercontent.com/rommapp/romm/master/docker-compose.example.yml"
  managed_volumes:
    - /path/to/library
    - /path/to/assets
    - /path/to/config

# Tengil's value-add: Storage optimization hints
storage_hints:
  "/path/to/library":
    profile: media  # 1M recordsize for large ROM files
    size_estimate: "500GB"
    why: "ROM files range from KB (NES) to GB (Switch)"
  
  "/path/to/config":
    profile: dev  # 8K recordsize for config files
    size_estimate: "1GB"

# Tengil's value-add: Share recommendations
share_recommendations:
  "/path/to/library":
    smb: true
    smb_name: "ROMs"
    read_only: false
```

### Using Compose Packages

```bash
# Initialize from compose package
tg init --package rom-manager-compose

# What happens:
# 1. Downloads docker-compose.yml from source
# 2. Analyzes volumes, secrets, ports
# 3. Applies storage hints (profiles, sizes)
# 4. Generates optimized tengil.yml

# Preview the generated config
tg diff

# Apply
tg apply
```

### Generated Output

From the compose package above, Tengil generates:

```yaml
version: 2
pools:
  tank:
    datasets:
      path-to-library:  # From /path/to/library
        profile: media  # 1M recordsize, lz4, atime=off
        consumers:
          - type: smb
            name: ROMs
            access: write
          - type: container
            name: romm
            access: write
            mount: /path/to/library
      
      path-to-config:
        profile: dev  # 8K recordsize for small files
        consumers:
          - type: container
            name: romm
            access: write
            mount: /path/to/config

containers:
  romm:
    memory: 2048
    cores: 2
    template: debian-12-standard
```

### What Tengil Adds Beyond Compose

1. **ZFS Optimization**: Right recordsize/compression for each volume type
2. **Permission Management**: Unified consumers model (container + SMB on same dataset)
3. **Share Configuration**: Automatic SMB/NFS setup
4. **Infrastructure Context**: Pool management, resource allocation, post-install

### Creating Your Own Compose Package

```yaml
name: My App
description: Description here
docker_compose:
  source: "https://example.com/docker-compose.yml"
  managed_volumes:
    - /data
    - /config

storage_hints:
  "/data":
    profile: media
    size_estimate: "1TB"
    why: "Explain optimization choice"

share_recommendations:
  "/data":
    smb: true
    smb_name: "MyAppData"
```

Then use: `tg init --package my-app`

### Compose vs Traditional Packages

**Traditional Package** (~200 lines):
- Define all datasets manually
- Specify all mounts
- Track upstream changes
- High maintenance

**Compose Package** (~50 lines):
- Reference upstream compose
- Add storage optimization hints
- Upstream tracks their own changes
- Low maintenance

### When to Use Compose Integration

✅ **Use when**:
- App has official docker-compose.yml
- You want to track upstream changes automatically
- App is primarily Docker-based
- You want minimal maintenance

❌ **Don't use when**:
- App is better suited for native LXC (use tteck scripts)
- You need complex custom configuration
- App doesn't have stable compose file

### Available Compose Packages

Currently available:
- `rom-manager-compose` - romM retro game collection manager

More coming in Phase 2: Jellyfin, Immich, qBittorrent, Home Assistant, Nextcloud.
