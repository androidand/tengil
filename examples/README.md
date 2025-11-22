# Tengil Example Configurations

This directory contains example `tengil.yml` configurations demonstrating various features and use cases.

## 🚀 Quick Start Examples

### Simple OCI Container
**File:** `test-simple.yml`
**Description:** Minimal OCI container deployment (nginx)
**Use Case:** Learning the basics

```bash
tg apply examples/test-simple.yml
```

### OCI Container with Full Config
**File:** `test-nginx-simple.yml`
**Description:** OCI nginx with explicit configuration
**Use Case:** Understanding all available options

### Jellyfin Media Server
**File:** `test-jellyfin.yml`
**Description:** Media server with GPU transcoding
**Use Case:** Production media streaming

## 📦 Package-Based Deployments

### Using Package Specs
**File:** `test-packages.yml`
**Description:** Deploy using pre-configured packages
**Use Case:** Quick deployment of popular apps

Available packages in `tengil/packages/`:
- `jellyfin-oci.yml` - Media server with GPU
- `plex-oci.yml` - Alternative media server
- `photoprism-oci.yml` - AI photo management
- `vaultwarden-oci.yml` - Password manager
- `paperless-ngx-oci.yml` - Document management
- `immich-oci.yml` - Photo backup (multi-container)
- `nextcloud-oci.yml` - File sync
- `homeassistant-oci.yml` - Home automation

## 🏗️ Advanced Examples

### Full Homelab Stack
**File:** `full-homelab.yml`
**Description:** Complete homelab with media, files, automation
**Use Case:** Production homelab deployment

### Docker Apps
**File:** `docker-apps.yml`
**Description:** Docker-in-LXC for compose-based apps
**Use Case:** Running Docker Compose stacks

### Phase Examples
- `phase2-simple.yml` - Basic auto-create containers
- `phase2-auto-create.yml` - Advanced auto-create
- `phase3-permissions.yml` - User permissions and sharing

## 🎯 Feature Demonstrations

### OCI Auto-Creation
**File:** `test-oci-auto.yml`
**Description:** Automatic OCI container provisioning

### Resource Pools
**File:** `resource-pools.yml`
**Description:** Multiple pools with different configurations

### Container Metadata
**File:** `container-metadata.yml`
**Description:** Labels, tags, and custom metadata

## 📖 Configuration Format

### OCI Containers (Recommended)

```yaml
pools:
  tank:
    datasets:
      apps:
        profile: dev
        containers:
          - name: myapp
            image: nginx:alpine  # Short form - defaults to docker.io
            cores: 2
            memory: 1024
            disk: 8
            env:
              KEY: "value"
            mounts:
              - source: /tank/data
                target: /data
```

### OCI with Explicit Registry

```yaml
containers:
  - name: myapp
    type: oci
    oci:
      image: nginx
      tag: alpine
      registry: docker.io  # Explicit
    cores: 2
    memory: 1024
    disk: 8
```

### LXC Containers (Legacy)

```yaml
containers:
  - name: myapp
    type: lxc
    template: debian-12-standard
    cores: 2
    memory: 1024
    disk: 8
    post_install:
      - docker
```

## 🔧 Testing Your Configuration

```bash
# Validate syntax
tg diff examples/test-simple.yml

# Dry-run (shows what would change)
tg apply examples/test-simple.yml --dry-run

# Apply changes
tg apply examples/test-simple.yml
```

## 📚 More Information

- [User Guide](../docs/USER_GUIDE.md) - Complete documentation
- [OCI Guide](../docs/OCI-GUIDE.md) - OCI-specific features
- [Package Specs](../tengil/packages/) - Pre-configured apps
