# Tengil - Declarative Proxmox NAS Management

> *"All makt åt Tengil, vår befriare!"*

Rule your Proxmox homelab with an iron fist through declarative YAML configuration.

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
          # Multiple format options:
          - name: jellyfin          # By container name
            mount: /media
            readonly: true
          - vmid: 101              # By VMID
            mount: /media
          - 'plex:/media:ro'       # String shorthand
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

### Current Powers

- ✅ **ZFS orchestration**: Create pools and datasets with optimized settings
- ✅ **Container discovery**: Query 100+ available LXC templates (`tg discover`)
- ✅ **Smart recommendations**: Match apps to actual Proxmox templates (`tg suggest`)
- ✅ **Bind mount management**: Auto-configure container access via pct
- ✅ **Share configuration**: Samba and NFS with proper permissions
- ✅ **Proxmox integration**: Register ZFS storage automatically
- ✅ **Idempotent operations**: Safe to run multiple times
- ✅ **Multi-pool support**: Manage multiple ZFS pools from one config

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

### Container Mounts

Tengil mounts ZFS datasets to **existing** LXC containers using multiple formats:

```yaml
datasets:
  media:
    containers:
      # By container name (recommended)
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

**Prerequisites (must exist before running Tengil):**
- ZFS pools must be created (`zpool create ...`)
- LXC containers must be created (`pct create ...`)
- Tengil will:
  - ✅ Create ZFS datasets
  - ✅ Configure Proxmox storage
  - ✅ Mount datasets to containers
  - ✅ Set up Samba/NFS shares
  - ❌ Does not create pools or containers (yet - Phase 2 coming)

**Quick Setup Guide:**
```bash
# 1. Create ZFS pool (if needed)
zpool create -o ashift=12 tank mirror /dev/sda /dev/sdb

# 2. Create LXC containers (if needed)
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
