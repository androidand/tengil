# Tengil User Guide

## Quick Start

```bash
# Install
pip install tengil

# Create config
tg init

# Preview changes
tg diff

# Apply configuration
tg apply
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

## Troubleshooting

### "Dataset already exists"
Tengil detects existing datasets and won't recreate them. Use `tg import` to generate config from existing setup.

### "Container not found"
Ensure the container exists in Proxmox before adding mounts. Tengil doesn't create containers.

### Cross-pool hardlinks warning
*arr apps (Sonarr, Radarr) need media on same pool for hardlinks. Don't split downloads and media across pools.
