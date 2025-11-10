<div align="center">

<img src="./docs/images/tengil-helm.png" alt="Tengil" width="200"/>

# Tengil

> *"All makt åt Tengil, vår befriare!"*

**Declarative infrastructure for Proxmox homelabs**

One YAML file. Storage + containers + shares.

[![Tests](https://img.shields.io/badge/tests-345%2F346%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

[Quick Start](#quick-start-2-minutes) •
[Packages](#available-packages) •
[Docs](docs/USER_GUIDE.md) •
[Examples](#configuration-example)

</div>

---

## What is Tengil?

**Infrastructure-as-code for Proxmox homelabs.** Get TrueNAS SCALE-like simplicity for storage + apps **without replacing your OS**.

```yaml
# tengil.yml
version: 2
pools:
  tank:
    datasets:
      media:
        profile: media              # ← ZFS optimized (1MB recordsize, lz4)
        containers:
          - name: jellyfin
            auto_create: true
            mount: /media
        shares:
          smb: Media               # ← Samba share
```

```bash
tg diff   # See what will change
tg apply  # Make it happen
```

**Result**: Storage + Jellyfin + share running in 2 commands.

---

## Why Tengil?

**You chose Proxmox for flexibility.** Now get TrueNAS-like simplicity for storage + apps.

<table>
<tr>
<th>Manual Proxmox</th>
<th>Tengil</th>
</tr>
<tr>
<td>

```bash
# 30+ minutes, 15+ commands
zfs create tank/media
zfs set recordsize=1M tank/media
zfs set compression=lz4 tank/media
pvesm add zfspool tank-media ...
nano /etc/samba/smb.conf
# ... (more manual config)
```

</td>
<td>

```yaml
# 2 minutes, 2 commands
media:
  profile: media
  shares:
    smb: Media
```

```bash
tg apply
```

</td>
</tr>
</table>

### Key Benefits

- ✅ **Reproducible**: `git commit tengil.yml` → restore anywhere
- ✅ **Optimized**: ZFS profiles auto-tuned for media/databases/downloads
- ✅ **Unified**: Storage + containers + shares in one place
- ✅ **Safe**: Preview changes with `tg diff` before applying
- ✅ **Trackable**: State stored in `.tengil.state.json`

---

## Quick Start (2 Minutes)

### Prerequisites

- **Proxmox VE** (7.x or 8.x)
- **ZFS pool** created
- **Python 3.10+** on your workstation

### Installation & First Deploy

```bash
# Install
git clone https://github.com/androidand/tengil.git
cd tengil
poetry install

# Deploy your first NAS
alias tg="poetry run python -m tengil.cli"
tg packages list              # Browse 13 packages
tg init --package nas-basic   # Interactive setup
tg diff                       # Preview changes
tg apply                      # Deploy to Proxmox
```

**Result:** ZFS datasets with SMB shares ready to mount from your Mac/PC.

📖 **[Complete installation guide & Mac mounting instructions →](docs/USER_GUIDE.md#installation)**

**What just happened:**
- ✅ Created optimized ZFS datasets (media, downloads, etc.)
- ✅ Downloaded LXC templates
- ✅ Created containers with proper resources
- ✅ Mounted storage with correct permissions
- ✅ Configured Samba shares
- ✅ Generated `tengil.yml` for version control

---

## Docker Compose Integration

Tengil uses upstream Docker Compose files as source of truth + adds ZFS storage optimization:

```bash
# Use curated compose files
tg init --package ai-workstation  # Ollama + Jupyter from compose_cache/

# Or analyze any compose file
tg compose analyze ./docker-compose.yml

# Tengil adds:
# - ZFS recordsize optimization (1M for media, 8K for databases)
# - Unified permissions (container + SMB share same data)
# - SMB/NFS share generation
# - LXC container management
```

**Resolution chain**: cache → upstream URL → generate from image → dockerfile

**Cached apps**: ollama, jupyter, jellyfin, immich, nextcloud

See [USER_GUIDE.md](docs/USER_GUIDE.md#docker-compose-integration) for details.

---

## Available Packages

**Storage** (Simple NAS):
- `nas-basic` - Samba shares only
- `nas-complete` - NAS + Nextcloud + Immich

**Media**:
- `media-server` - Jellyfin + organized media
- `download-station` - qBittorrent + *arr stack (Sonarr, Radarr, Prowlarr)

**Development**:
- `ai-workstation` - Ollama + Jupyter + GPU support
- `devops-playground` - Gitea + CI/CD + monitoring

**Automation**:
- `home-automation` - Home Assistant + Node-RED + MQTT

**Network**:
- `remote-access` - WireGuard + nginx-proxy + Authelia
- `privacy-fortress` - Pi-hole + Vaultwarden + CrowdSec

**Collaboration**:
- `family-hub` - Shared calendars + tasks + recipes + photos

**Gaming**:
- `gaming-station` - ROM storage + game streaming
- `rom-manager-compose` - romM (Docker Compose integration example)

---

## What Makes Tengil Different

### 1. Storage-First Philosophy

**Most tools**: "Container needs 50GB" → allocate generic volume

**Tengil**: "Media needs 1MB recordsize for sequential reads" → optimize storage first

```yaml
datasets:
  media:
    profile: media  # recordsize=1M, compression=lz4, atime=off
    consumers:
      - container: jellyfin
        mount: /media
      - share: smb/Media
# Tengil handles: ZFS props, mount flags, Samba config, permissions
```

**Real impact**:
- 30% faster sequential reads (optimized recordsize)
- 3-4x space savings for code repos (heavy compression)
- Automatic permission management across containers + shares

### 2. Unified Permissions

**The pain**: "Jellyfin reads `/media`, SMB share writes to it, Immich also needs access"

Manually: Configure ZFS ACLs, pct mount flags, Samba permissions, user mappings.

**Tengil**: Just declare consumers, permissions handled automatically.

### 3. Terraform-lite Workflow

```bash
tg diff      # Plan: see what will change
tg apply     # Apply: make it happen
tg rollback  # Undo: restore from checkpoint
```

State tracked in `.tengil.state.json`. Version control with git.

### 4. Docker Compose Integration

Use upstream compose files + add Tengil's storage optimization:

```yaml
# Old way: Maintain 200+ line package
# New way: Reference upstream + add hints (50 lines)

docker_compose:
  cache: "compose_cache/immich/docker-compose.yml"  # Curated
  source: "https://github.com/.../docker-compose.yml"  # Fallback

storage_hints:
  "/photos":
    profile: media
    size_estimate: "2TB"
```

**Why this matters**:
- ✅ Upstream maintains compose (not you)
- ✅ Tengil adds ZFS optimization (what compose can't do)
- ✅ 75% less YAML to write
- ✅ Works with any Docker Compose app

---

## What Tengil Manages

### ✅ Handles

**Storage**:
- ZFS dataset creation with optimized properties
- Proxmox storage registration
- Dataset profiles (media, dev, backups, docker)

**Compute**:
- LXC container creation from templates
- Container resource allocation (CPU, RAM)
- Container lifecycle (start/stop)
- Template auto-download

**Integration**:
- Bind mount configuration (dataset → container)
- Samba/NFS share setup
- Docker + Portainer installation
- Docker Compose deployment

**Operations**:
- State tracking (what Tengil created)
- Diff preview (see changes before apply)
- Automatic checkpoints (recovery snapshots)
- Idempotent operations (safe to re-run)

### ❌ Doesn't Handle

- **VMs**: LXC only (use Proxmox UI for VMs)
- **Networking**: Firewalls, VLANs (use Proxmox UI)
- **App config**: Jellyfin settings, Sonarr indexers (use app web UI)
- **Backups**: Snapshot scheduling (use Proxmox Backup Server)
- **Multi-server**: Clustering, HA (use Ansible)

**Tengil's sweet spot**: Infrastructure layer (storage + compute + connectivity)

---

## CLI Reference

### Package Management
```bash
tg packages list                    # List all 13 packages
tg packages list --category media   # Filter by category
tg packages show nas-complete       # Show package details
```

### Configuration
```bash
tg init --package media-server      # Initialize from package (interactive)
tg init --package nas-complete --non-interactive  # Use defaults
tg diff                             # Preview changes
tg apply                            # Apply configuration
tg apply --yes                      # Skip confirmation
tg apply --dry-run                  # Show plan without executing
```

### Docker Compose
```bash
tg compose analyze ./docker-compose.yml  # Analyze compose file
tg compose validate ./compose.yml        # Validate Tengil compatibility
tg compose resolve ai-workstation        # Test package resolution
```

### Discovery
```bash
tg discover --containers            # List existing containers
tg discover --docker-containers     # Show running Docker containers
tg discover --compose-reverse abc123  # Reverse-engineer container to tengil.yml
```

### State Management
```bash
tg rollback --to 2025-11-10         # Restore from checkpoint
tg snapshot --name before-upgrade   # Create manual snapshot
```

---

## Configuration Example

**Simple media server:**

```yaml
version: 2
pools:
  tank:
    datasets:
      media:
        profile: media              # 1M recordsize for video files
        containers:
          - name: jellyfin
            auto_create: true
            template: debian-12-standard
            mount: /media
            readonly: true          # Safety: prevent accidental deletion
            memory: 4096
            cores: 2
            post_install: tteck/jellyfin  # Auto-install Jellyfin
        shares:
          smb:
            name: Media
            browseable: yes
```

**With Docker Compose:**

```yaml
version: 2
pools:
  tank:
    datasets:
      photos:
        profile: media
        containers:
          - name: immich
            auto_create: true
            mount: /photos

containers:
  immich:
    memory: 8192
    cores: 4
    docker_compose:
      cache: "compose_cache/immich/docker-compose.yml"
      image: "ghcr.io/immich-app/immich-server:release"  # Fallback

storage_hints:
  "/photos":
    profile: media
    size_estimate: "2TB"
```

---

## Feature Status

**✅ Production Ready**:
- ZFS dataset management
- Proxmox storage integration
- Samba/NFS shares
- Multi-pool support
- Docker Compose integration
- State tracking
- Profile system

**⚠️ Experimental** (test first):
- Container auto-creation
- Template auto-download
- Post-install scripts (Docker, Portainer, tteck)
- Docker Compose deployment to containers

**🚧 Planned**:
- State import (`tg import`)
- Pool analysis (`tg plan-pools`)
- Backup integration

---

## Troubleshooting

**"Pool 'tank' not found"**:
```bash
zpool list  # Check pool name
# Edit tengil.yml to match actual pool name
```

**"Template not found"**:
```bash
pveam available | grep debian
pveam download local debian-12-standard_12.2-1_amd64.tar.zst
```

**"Container already exists"**:
```bash
pct list  # Check existing VMIDs
# Edit tengil.yml, change vmid field
```

**"Permission denied"**:
```bash
# Tengil needs root for ZFS/Proxmox operations
```

---

## Production Readiness

**✅ Safe for production**: ZFS operations, mount management, share configuration

**⚠️ Test first**: Container auto-creation, Docker installation, compose deployment

**Before production**:
1. Test in dev Proxmox environment
2. Always run `tg diff` before `tg apply`
3. Backup container configs: `pct config <VMID>`
4. Version control your `tengil.yml` with git
5. Use Proxmox Backup Server for data backups

**Safety**: Tengil creates but never destroys. Your data is safe.

---

## Requirements

- Proxmox VE 7.x or 8.x
- Python 3.10+
- ZFS pool (create once: `zpool create tank ...`)
- Root/sudo access

## Documentation

📖 **[Complete User Guide](docs/USER_GUIDE.md)** - Configuration reference, Docker Compose integration, troubleshooting

### Quick Links

- **Getting Started**: [Installation](docs/USER_GUIDE.md#installation) | [First Deploy](docs/USER_GUIDE.md#first-deploy---nas-shares)
- **Configuration**: [Single Pool](docs/USER_GUIDE.md#single-pool-setup) | [Multi Pool](docs/USER_GUIDE.md#multi-pool-setup) | [Profiles](docs/USER_GUIDE.md#built-in-profiles)
- **Tasks**: [Add Containers](docs/USER_GUIDE.md#adding-a-container-mount) | [Add Shares](docs/USER_GUIDE.md#adding-smb-share) | [Post-Install](docs/USER_GUIDE.md#post-install-automation)
- **Advanced**: [Docker Compose](docs/USER_GUIDE.md#docker-compose-integration) | [Troubleshooting](docs/USER_GUIDE.md#troubleshooting)

---

## License

MIT

## Credits

Named after Tengil from Astrid Lindgren's "The Brothers Lionheart" - who ruled with absolute control from his fortress.

> **"All makt åt Tengil, vår befriare!"**
> *("All power to Tengil, our liberator!")*

Like the tyrant who commanded Cherry Valley, this Tengil commands your homelab infrastructure from a single YAML file. The difference? This Tengil serves you.
