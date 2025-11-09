# Tengil - Declarative Proxmox NAS Management

> *"All makt åt Tengil, vår befriare!"*

Rule your Proxmox homelab with an iron fist through declarative YAML configuration.

## Real Talk: What This Actually Does

**You have a fresh Proxmox server. What can Tengil do RIGHT NOW?**

1. **Create your ZFS pool** (you do this once manually: `zpool create tank ...`)
2. **Write one YAML file** defining your datasets, containers, and shares
3. **Run `tg apply`** and Tengil:
   - Creates all your ZFS datasets with optimized settings
   - Downloads LXC templates automatically
   - Creates and starts containers
   - Mounts datasets into containers
   - Configures Samba/NFS shares
   - Tracks everything in state

**What you still configure yourself:**
- Apps inside containers (Jellyfin, Nextcloud, etc.) - install them normally after containers exist
- Network settings, firewall rules - use Proxmox UI or manual config
- Backups - use Proxmox Backup Server or your own solution
- VMs - Tengil only handles LXC containers, not VMs

**What Tengil gives you:**
- **Infrastructure as code** - your entire storage/container setup in one file
- **Reproducibility** - blow it away, run `tg apply`, back to working state
- **No scattered pct commands** - everything declarative
- **Safe operations** - diff before apply, idempotent, never destroys data

## Why?

**The Problem**: Running Proxmox as a NAS requires tedious manual work:
- Creating ZFS datasets with correct properties
- Configuring Proxmox storage
- Setting up container bind mounts via `pct set`
- Editing Samba/NFS configs
- Managing permissions
- Keeping track of what you've created

**The Solution**: One YAML file, one command. Total control.

Like Tengil commanded Cherry Valley from his fortress in Karmanjaka, you command your entire infrastructure from a single configuration file. No more scattered commands, no more forgotten mounts, no more manual tedium.

## Quick Start

```bash
# Install
pip install tengil

# Generate config
tg init

# Preview changes
tg diff

# Apply
tg apply
```

## Example Configuration

```yaml
version: 2
pools:
  tank:
    type: zfs
    datasets:
      media:
        profile: media
        containers:
          # Phase 2: Auto-create containers
          - name: jellyfin
            auto_create: true
            template: debian-12-standard
            mount: /media
            readonly: true
            resources:
              memory: 2048
              cores: 2
          
          # Phase 1: Mount to existing containers
          - name: plex
            mount: /media
            readonly: true
        shares:
          smb:
            name: Media
            browseable: yes
            guest_ok: false

      downloads:
        profile: downloads
        containers:
          - name: qbittorrent
            mount: /downloads
          - name: transmission
            mount: /downloads
            readonly: false        # Read-write access
```

## What It Does

Tengil brings **order and control** to your infrastructure:

**Declare** your desired state → **Review** with `tg diff` → **Execute** with `tg apply`

- **ZFS orchestration**: Create pools and datasets with optimized settings
- **Container auto-creation**: Automatically create LXC containers from templates
- **Template management**: Auto-download missing LXC templates
- **Container lifecycle**: Start/stop containers automatically
- **Bind mount management**: Auto-configure container access via pct
- **Container discovery**: Query 100+ available LXC templates (`tg discover`)
- **Smart recommendations**: Match apps to actual Proxmox templates (`tg suggest`)
- **Share configuration**: Samba and NFS with proper permissions
- **Proxmox integration**: Register ZFS storage automatically
- **Idempotent operations**: Safe to run multiple times
- **Multi-pool support**: Manage multiple ZFS pools from one config

## Built-in Profiles

- **media** - Movies, photos (1M recordsize, compression lz4)
- **dev** - App configs (8K recordsize, compression lz4)
- **downloads** - Mixed files (128K recordsize)
- **backups** - Compressed backups (zstd compression)

Override any ZFS property:

```yaml
datasets:
  custom:
    profile: media
    zfs:
      recordsize: 512K
      compression: zstd
```

## Features

### Multi-Pool Support

```yaml
pools:
  rpool:    # Fast NVMe
    datasets:
      appdata: ...
      databases: ...
  
  tank:     # Bulk storage
    datasets:
      media: ...
      backups: ...
```

### Safe OS Pool Usage

Tengil warns about Proxmox-reserved paths on `rpool`:
- `rpool/ROOT` - OS (protected)
- `rpool/data` - VMs (protected)

Recommends using `rpool/tengil/*` namespace for clarity.

### Container Management

Tengil can automatically create and configure LXC containers:

```yaml
datasets:
  media:
    containers:
      - name: jellyfin
        auto_create: true
        template: debian-12-standard
        mount: /media
        readonly: true
        resources:
          memory: 2048
          cores: 2
          disk: 16G
        network:
          bridge: vmbr0
          ip: dhcp
```

**What happens:**
1. Template downloaded if missing
2. Container created with specified resources
3. Container started
4. Dataset mounted to container

**Mount to existing containers:**

```yaml
datasets:
  media:
    containers:
      # By container name
      - name: jellyfin
        mount: /media
        readonly: true
      
      # By VMID
      - vmid: 100
        mount: /backup
      
      # String shorthand
      - 'plex:/media:ro'
```

**Finding Container Info:**
```bash
# List all containers
pct list

# Get container hostname (for 'name' field)
pct config 100 | grep hostname

# Get container status
pct status 100
```

**Note:** Containers must exist before running `tg apply`. Tengil handles the mounting automatically.

### SMB Shares

```yaml
datasets:
  media:
    shares:
      smb:
        name: Media           # Share name (no path needed - auto-calculated)
        browseable: yes
        guest_ok: false
```

### NFS Exports

```yaml
datasets:
  media:
    shares:
      nfs:
        allowed: "192.168.1.0/24"
        options: "rw,sync,no_root_squash"
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) - Complete reference
- [Contributing](CONTRIBUTING.md) - Development guide

## Troubleshooting

### Container not found
```
WARNING: Container 'jellyfin' not found - skipping mount
```
**Solution:** Verify container exists and name matches hostname:
```bash
pct list                          # List all containers
pct config 100 | grep hostname    # Get hostname for VMID 100
```

### Mount already exists
Tengil is idempotent - if mount already exists, it skips it:
```
✓ Mount already exists: /tank/media → jellyfin:/media
```
This is normal and safe.

### Container name vs VMID
- Use `name:` for container hostname (e.g., "jellyfin")
- Use `vmid:` for container ID (e.g., 100)
- Both work, name is more readable

### Check current mounts
```bash
pct config 100               # Show full container config
pct config 100 | grep mp     # Show only mount points
```

## Requirements

**System Requirements:**
- Proxmox VE 7.0+ (or Linux with ZFS)
- Python 3.8+
- Root access (for ZFS and Proxmox operations)

**What Tengil Manages:**
- ZFS datasets (automatic creation)
- LXC containers (automatic creation from templates)
- LXC templates (automatic download)
- Container bind mounts (automatic configuration)
- Proxmox storage (automatic registration)
- Samba/NFS shares (automatic setup)

**What you need to create manually:**
- ZFS pools (one-time setup)

**Quick Setup Guide:**

Automatic containers (recommended):
```bash
# 1. Create ZFS pool (manual - one time)
zpool create -o ashift=12 tank mirror /dev/sda /dev/sdb

# 2. Configure Tengil (containers created automatically)
tg init
vim /etc/tengil/tengil.yml
# Add auto_create: true to containers

# 3. Apply - Tengil creates everything
tg diff
tg apply
```

Manual containers (old way):
```bash
# 1. Create ZFS pool
zpool create -o ashift=12 tank mirror /dev/sda /dev/sdb

# 2. Create LXC containers manually
pct create 100 local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst \
  --hostname jellyfin \
  --memory 2048 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp

# 3. Use Tengil to manage datasets and mounts
tg init
tg diff
tg apply
```

## License

MIT

## Credits

Named after Tengil from Astrid Lindgren's "The Brothers Lionheart" - the tyrant who ruled Karmanjaka with absolute control.

> **"All makt åt Tengil, vår befriare!"**  
> *("All power to Tengil, our liberator!")*

In the saga, Tengil conquered Cherry Valley with his fire-breathing dragon Katla, ruling with an iron fist from his fortress in Karmanjaka. Like the fictional overlord who maintained strict control over his domain, this tool orchestrates your Proxmox infrastructure with unwavering authority - though for good, not evil.

Just as Tengil commanded Cherry Valley from Karmanjaka, this Tengil commands your homelab infrastructure from a single YAML file. The difference? This Tengil serves you, bringing order and automation to your storage empire.
