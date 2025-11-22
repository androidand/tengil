# Tengil User Guide

Complete reference for using Tengil to manage Proxmox infrastructure.

## Installation

Tengil runs **on your Proxmox server** and manages storage/containers locally. Choose your installation method:

### Method 1: Production Install (from GitHub)

**Easiest for most users.** Installs latest release from GitHub to `/opt/tengil`.

```bash
# SSH to your Proxmox server
ssh root@proxmox-ip

# Run installer
curl -fsSL https://raw.githubusercontent.com/androidand/tengil/main/scripts/install.sh | sudo bash

# Reload shell
source ~/.bashrc

# Verify
tg version
```

**What it does:**
- Installs dependencies (`python3-venv`, `python3-pip`, `git`)
- Clones repo to `/opt/tengil`
- Creates Python venv and installs packages
- Adds `tg` alias to `~/.bashrc`
- Creates `~/tengil-configs/` working directory

---

### Method 2: Development Install (from local repo)

**For contributors or testing local changes.** Copies your local repo to `/opt/tengil`.

```bash
# On your workstation, clone and prepare
git clone https://github.com/androidand/tengil.git
cd tengil

# Copy to Proxmox
scp -r . root@proxmox-ip:/tmp/tengil-local

# SSH to Proxmox
ssh root@proxmox-ip

# Install from local copy
cd /tmp/tengil-local
sudo ./scripts/install.sh --local

# Reload shell
source ~/.bashrc

# Verify
tg version
```

**Use case:** Testing changes before pushing to GitHub

---

### Method 3: Quick Dev Test (temporary)

**For quick testing without permanent install.** Installs to `/tmp/tengil-dev` with mock mode enabled.

```bash
# On Proxmox (or copy repo as above)
cd /path/to/tengil
sudo ./scripts/install.sh --dev

# Test without installing permanently
cd /tmp/tengil-dev
export TG_MOCK=1
.venv/bin/poetry run tg packages list
.venv/bin/poetry run tg diff
```

---

## Drift & Reality Snapshots

Tengil encourages a “hybrid” workflow where GUI/manual tweaks and declarative YAML stay in sync:

1. After making GUI changes (e.g., tweaking mounts in Proxmox), run `tg scan` to capture the new reality snapshot.
2. `tg diff` always compares your YAML plan plus a drift summary against the last scan, so you know what changed outside Tengil.
3. `tg apply` supports drift-aware options:
   - Run `tg verify` before plans/applies if you just want to validate the YAML + host resources without touching anything.
   - `--prefer-gui`: when safe drift is detected, prefer reality (update YAML) instead of forcing YAML on Proxmox.
   - `--no-drift-auto-merge`: require interactive confirmation for every drift item, even harmless ones.

When dangerous drift is detected, the CLI highlights it (red section) and prompts before continuing. If you haven’t run `tg scan` since making manual edits, the CLI reminds you to do so.

> Tip: `tg plan` is an alias for `tg diff` for people coming from Terraform. Use whichever name matches your muscle memory.

> Hint: use `tg repo init --path ~/tengil-configs` to bootstrap a Git repo (with sensible `.gitignore`) the first time you create a config, and `tg status` to check what changed before committing/applying.

**Use case:** Quick testing, development, CI/CD  
**Note:** `/tmp` is cleared on reboot

---

### Comparison

| Feature | Production | Development | Quick Test |
|---------|-----------|-------------|------------|
| Source | GitHub | Local repo | Local repo |
| Location | `/opt/tengil` | `/opt/tengil` | `/tmp/tengil-dev` |
| Persistent | ✅ Yes | ✅ Yes | ❌ No (tmp) |
| Shell alias | ✅ Yes | ✅ Yes | ❌ No |
| Mock mode | ❌ No | ❌ No | ✅ Yes |
| Use case | Production | Development | Testing |

---

## Quick Start

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

## Importing Existing Infrastructure

If you already have ZFS datasets and containers on Proxmox, use `tg import` to generate a tengil.yml from your existing setup. This is useful for:
- Adopting Tengil on existing homelab infrastructure
- Migrating manual configuration to declarative YAML
- Creating backups of current infrastructure state
- Understanding current system configuration

### Basic Import

```bash
# Scan pool and generate config
tg import tank

# Output: tengil-imported.yml (review before using)
```

The importer scans your Proxmox system and generates a complete tengil.yml with:
- All ZFS datasets in the specified pool
- ZFS properties (compression, recordsize, atime, sync)
- Inferred dataset profiles based on properties
- All LXC containers (both OCI and traditional)
- Container specs (cores, memory, disk, mounts, env vars)
- Mount points and bind mounts

### Import Options

```bash
# Save to specific file
tg import tank -o tengil.yml

# Import only specific containers (by VMID range)
tg import tank --container 200-210

# Preview without writing (dry-run)
tg import tank --dry-run

# Show detailed dataset/container tables
tg import tank --verbose
```

### What Gets Detected

**ZFS Datasets:**
- Compression algorithm (off, lz4, gzip, zstd, etc.)
- Recordsize (128K, 1M, etc.)
- Access time tracking (atime on/off)
- Sync behavior (standard, always, disabled)
- Inferred profile (media, backups, documents)

**Container Detection:**
- **Container Type**: Automatically detects OCI vs LXC
  - OCI: rootfs contains `subvol` or `oci:` prefix
  - LXC: traditional template-based rootfs
- **Resources**: cores, memory, disk size
- **Mounts**: All mount points (mp0, mp1, mp2, etc.)
- **Environment Variables**: Extracted from `lxc.environment.*`
- **Network**: Bridge, IP, gateway configuration

### Container Type Detection

The importer intelligently detects whether containers are OCI or LXC:

**OCI Containers:**
```yaml
- name: jellyfin
  type: oci
  image: jellyfin/jellyfin:latest
  cores: 4
  memory: 4096
  disk: 16
  auto_create: false  # Already exists
```

**LXC Containers:**
```yaml
- name: debian-host
  type: lxc
  template: debian-12-standard
  cores: 2
  memory: 2048
  disk: 8
  auto_create: false  # Already exists
```

### Example Output

```yaml
pools:
  tank:
    type: zfs
    datasets:
      media:
        profile: media
        zfs:
          compression: lz4
          recordsize: 1M
          atime: off
          sync: standard
        containers:
          - name: jellyfin
            type: oci
            image: jellyfin/jellyfin:latest
            cores: 4
            memory: 4096
            disk: 16
            auto_create: false  # Don't recreate existing
            env:
              JELLYFIN_PublishedServerUrl: http://jellyfin.local
            mounts:
              - source: /tank/media
                target: /media
                readonly: true

      appdata:
        profile: appdata
        zfs:
          compression: lz4
          recordsize: 128K
          atime: off
        containers:
          - name: nextcloud
            type: lxc
            template: debian-12-standard
            cores: 2
            memory: 4096
            disk: 32
            auto_create: false
            mounts:
              - source: /tank/appdata/nextcloud
                target: /var/www/nextcloud/data
                readonly: false
```

### Migration Workflow

**Step 1: Import Current State**
```bash
tg import tank -o tengil.yml --verbose
```

This generates a complete snapshot of your current infrastructure.

**Step 2: Review Generated Config**
```bash
cat tengil.yml

# Check:
# - Dataset profiles match your usage (media, appdata, backups, etc.)
# - Container specs are accurate
# - auto_create is set to false for existing containers
# - Mounts are correctly detected
```

**Step 3: Adjust if Needed**

Common adjustments:
- **Fix profiles**: If inference was wrong, change `profile: media` to correct type
- **Set auto_create**: All containers default to `auto_create: false` (safe)
- **Add missing shares**: Import doesn't detect Samba/NFS shares, add manually
- **Adjust mounts**: Verify mount points match your needs

**Step 4: Validate**
```bash
tg diff --config tengil.yml

# Should show minimal diff (mostly "already exists")
# Any CREATE operations indicate missing resources
```

**Step 5: Apply Additions**
```bash
tg apply --config tengil.yml

# Tengil will:
# - Skip existing datasets (idempotent)
# - Skip existing containers (auto_create: false)
# - Add any missing mounts
# - Create any missing shares (if you added them)
```

### Profile Inference Logic

The importer infers dataset profiles from ZFS properties:

| Properties | Inferred Profile |
|-----------|-----------------|
| recordsize=1M, compression=off | `media` |
| recordsize=128K, compression=zstd | `backups` |
| recordsize=128K, compression=lz4 | `documents` |
| Default | `media` |

**Tip**: Always review and adjust profiles to match your actual usage patterns.

### Filtering by Container Range

For large deployments, import incrementally:

```bash
# Import only containers 200-210
tg import tank --container 200-210 -o jellyfin-cluster.yml

# Import only containers 100-150
tg import tank --container 100-150 -o app-cluster.yml

# Import single container
tg import tank --container 205 -o jellyfin.yml
```

### Dry Run Mode

Preview what would be generated without writing files:

```bash
tg import tank --dry-run

# Shows:
# - Dataset table (name, profile, compression, recordsize)
# - Container table (VMID, name, status, type)
# - Generated YAML preview
# - Would write to: tengil-imported.yml
```

### Environment Variables

The importer extracts environment variables from container configs:

**Proxmox Config:**
```
lxc.environment.PUID: 1000
lxc.environment.PGID: 1000
lxc.environment.TZ: America/New_York
```

**Generated YAML:**
```yaml
env:
  PUID: "1000"
  PGID: "1000"
  TZ: "America/New_York"
```

### Tips & Best Practices

**✅ Do:**
- Always review generated config before applying
- Set `auto_create: false` for existing containers (default)
- Verify profiles match actual usage patterns
- Add missing Samba/NFS shares manually
- Use `--dry-run` first to preview
- Filter by container range for large setups

**❌ Don't:**
- Set `auto_create: true` for existing containers (will fail)
- Trust profile inference blindly (validate first)
- Skip the diff step (always run `tg diff` before `tg apply`)
- Import without backing up existing config

### Limitations

**Not Detected:**
- Samba/NFS share configurations (add manually)
- Container network details beyond basic IP/gateway
- Proxmox resource pools (add manually if needed)
- Container startup order/delay settings

**Known Issues:**
- Profile inference is best-effort (validate manually)
- OCI image tags may be `latest` if not determinable
- Private registries require manual registry field addition

### Advanced: Import + Git Workflow

```bash
# 1. Import existing infrastructure
cd ~/tengil-configs
tg import tank -o tengil.yml

# 2. Initialize Git repo
tg repo init --path .

# 3. Commit initial state
git add tengil.yml
git commit -m "Initial import from existing Proxmox infrastructure"

# 4. Make changes
$EDITOR tengil.yml

# 5. Preview changes
tg diff

# 6. Apply and track
tg apply
git commit -am "Add Jellyfin media shares"
git push
```

This workflow lets you track infrastructure changes over time with full version history.

## Troubleshooting

### "Dataset already exists"
Tengil detects existing datasets and won't recreate them. Use `tg import` to generate config from existing setup, or manually add the dataset to your tengil.yml with matching properties.

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
