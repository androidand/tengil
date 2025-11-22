# OCI Container Support Guide

Tengil supports running OCI (Open Container Initiative) containers directly on Proxmox VE 9.1+, leveraging Proxmox's native OCI support. This provides a lightweight alternative to full VMs while maintaining excellent integration with Proxmox features.

## Quick Start

### Pulling Images

```bash
# Pull from Docker Hub (official images)
tg oci pull nginx:alpine
tg oci pull redis:latest

# Pull from Docker Hub (user/org images)
tg oci pull linuxserver/jellyfin:latest

# Pull from GitHub Container Registry
tg oci pull ghcr.io/home-assistant/home-assistant:stable

# Pull from Quay.io
tg oci pull quay.io/prometheus/prometheus:latest
```

### Listing Cached Images

```bash
# Table format (default)
tg oci list

# JSON format
tg oci list --format json
```

### Creating Containers

**Option 1: Declarative (Recommended)**

Create a YAML spec:

```yaml
# my-app.yml
---
version: v1

proxmox:
  host: 192.168.1.42
  verify_ssl: false
  node: pve

pools:
  tank:
    datasets:
      webapps:
        profile: web
        containers:
          - name: my-nginx
            type: oci          # Enables OCI backend
            vmid: 200
            hostname: nginx
            cores: 2
            memory: 1024
            disk: 8
            auto_create: true
            oci:
              image: nginx
              tag: alpine
            network:
              bridge: vmbr0
              ip: dhcp
            unprivileged: true
```

Apply it:

```bash
tg apply -c my-app.yml
```

**Option 2: Manual (Testing/Development)**

```bash
# Pull image
tg oci pull nginx:alpine

# Create container manually
pct create 200 local:vztmpl/nginx-alpine.tar \
  --hostname nginx \
  --cores 2 \
  --memory 1024 \
  --rootfs tank:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --unprivileged 1

# Start it
pct start 200
```

## Features

### GPU Passthrough

Enable hardware transcoding for media servers:

```yaml
gpu:
  passthrough: true
  type: intel  # intel, nvidia, amd, or auto
```

The system will automatically:
- Detect available GPUs if `type: auto`
- Pass through `/dev/dri/card0` and `/dev/dri/renderD128` (Intel)
- Set appropriate permissions (`cgroup2.devices`)

### ZFS Mounts

Mount host datasets into containers:

```yaml
mounts:
  - source: /tank/media
    target: /media
    readonly: true
  
  - source: /tank/appdata/jellyfin
    target: /config
    readonly: false
```

### Environment Variables

Pass environment variables to containers:

```yaml
env:
  TZ: "America/New_York"
  PUID: "1000"
  PGID: "1000"
  ADMIN_PASSWORD: "changeme"
```

### Network Configuration

```yaml
network:
  bridge: vmbr0
  ip: dhcp                    # Or static: 192.168.1.100/24
  gateway: 192.168.1.1        # Optional for static IPs
  firewall: true
```

## App Catalog

Tengil includes 31+ pre-configured applications. Browse and search:

```bash
# List popular apps (per category)
tg oci catalog

# List all apps
tg oci catalog --all

# List apps in a category
tg oci catalog --category media

# Search for apps
tg oci search media
tg oci search photo

# Show details for an app
tg oci info jellyfin
```

### Popular Apps

**Media Servers:**
- Jellyfin - Media server with transcoding
- Plex - Media server and streaming
- Emby - Media server alternative

**Photo Management:**
- Immich - Self-hosted photo backup
- PhotoPrism - AI-powered photo management
- Photoview - Simple photo gallery

**File Storage:**
- Nextcloud - File sync and collaboration
- Seafile - High-performance file sync
- FileBrowser - Web-based file manager

**Home Automation:**
- Home Assistant - Home automation platform
- Mosquitto - MQTT message broker
- Zigbee2MQTT - Zigbee to MQTT bridge

**Document Management:**
- Paperless-ngx - Document management with OCR
- Calibre-web - eBook library management
- BookStack - Wiki and documentation

**Password Managers:**
- Vaultwarden - Bitwarden-compatible password manager
- Passbolt - Team password manager

**Monitoring:**
- Portainer - Container management UI
- Uptime Kuma - Uptime monitoring
- Grafana - Metrics visualization
- Prometheus - Metrics collection

**Network Services:**
- Pi-hole - Network-wide ad blocking
- AdGuard Home - Network ad/tracker blocker
- Nginx - Web server and reverse proxy
- Traefik - Modern reverse proxy

## Package Specs

Use pre-configured package specs for common apps:

```bash
# Copy example and customize
cp packages/jellyfin-oci.yml my-jellyfin.yml
vim my-jellyfin.yml

# Apply
tg apply -c my-jellyfin.yml
```

Available specs:
- Media/Photos: `jellyfin-oci.yml`, `plex-oci.yml`, `emby-oci.yml`, `photoprism-oci.yml`, `photoview-oci.yml`, `navidrome-oci.yml`, `audiobookshelf-oci.yml`, `immich-oci.yml`, `librephotos-oci.yml`
- Files/Docs: `nextcloud-oci.yml`, `seafile-oci.yml`, `filebrowser-oci.yml`, `paperless-ngx-oci.yml`, `calibre-web-oci.yml`, `bookstack-oci.yml`, `wikijs-oci.yml`
- Automation/Network: `homeassistant-oci.yml`, `mosquitto-oci.yml`, `zigbee2mqtt-oci.yml`, `nginx-oci.yml`, `traefik-oci.yml`, `adguardhome-oci.yml`
- Monitoring/Ops: `portainer-oci.yml`, `prometheus-oci.yml`, `grafana-oci.yml`, `uptimekuma-oci.yml`
- Security/RSS/Recipes: `vaultwarden-oci.yml`, `passbolt-oci.yml`, `freshrss-oci.yml`, `miniflux-oci.yml`, `tandoor-oci.yml`, `mealie-oci.yml`

## Cache Cleanup

Remove cached OCI templates when you need space:

```bash
# Remove a specific image/tag
tg oci remove alpine:latest

# Remove a pattern (wildcards supported)
tg oci remove alpine:*

# Prune all unused templates (keeps templates referenced by containers)
tg oci prune --dry-run   # show what would be removed
tg oci prune             # delete after confirmation
```

Safety checks:
- Refuses to delete templates referenced by existing containers
- Shows total size to be freed and prompts unless `--force` is set

## Registry Authentication

For private registries:

```bash
# Login to registry
tg oci login ghcr.io --username myuser

# Pull private image
tg oci pull ghcr.io/myorg/private-app:latest

# Logout
tg oci logout ghcr.io
```

## Best Practices

### Security

1. **Use unprivileged containers** - Default and recommended
2. **Run as non-root** - Use PUID/PGID environment variables
3. **Readonly mounts** - For media libraries
4. **Network isolation** - Consider VLANs for IoT devices
5. **Regular updates** - Pull new image versions regularly

### Performance

1. **GPU passthrough** - For transcoding workloads
2. **ZFS compression** - Enable on dataset for better performance
3. **Memory allocation** - Start conservative, monitor, adjust
4. **Storage placement** - Use SSD for appdata, HDD for media

### Resource Planning

**Typical allocations:**

| App Type | Cores | Memory | Disk | Notes |
|----------|-------|--------|------|-------|
| Web servers | 1-2 | 512MB | 4-8GB | Nginx, Caddy |
| Media servers | 4+ | 4GB+ | 16GB+ | Jellyfin, Plex (with GPU) |
| Photo management | 4+ | 4GB+ | 32GB+ | PhotoPrism, Immich (AI processing) |
| Document management | 2+ | 2GB+ | 16GB+ | Paperless-ngx (OCR) |
| Password managers | 1 | 512MB | 8GB | Vaultwarden |
| Home automation | 2 | 1GB | 8-16GB | Home Assistant |
| Monitoring | 1-2 | 512MB-1GB | 8GB | Uptime Kuma, Grafana |

## Troubleshooting

### Image Pull Failures

```bash
# Check network connectivity
ping registry-1.docker.io

# Verify authentication
tg oci logout docker.io
tg oci login docker.io

# Check Proxmox skopeo installation
ssh root@proxmox "which skopeo"
```

### Container Won't Start

```bash
# Check container config
pct config 200

# View logs
pct exec 200 -- tail -f /var/log/syslog

# Check entrypoint
pct config 200 | grep entrypoint
```

### GPU Not Detected

```bash
# On Proxmox host, verify GPU
lspci | grep VGA

# Check device permissions
ls -la /dev/dri/

# Verify inside container
pct exec 200 -- ls -la /dev/dri/
```

### Mount Permission Issues

```bash
# Check ownership on host
ls -la /tank/media

# Adjust UID/GID in container
# Set PUID/PGID environment variables to match host user
```

## Limitations

- **No build support** - Tengil pulls pre-built images only
- **Single registry per image** - Specify registry in image name
- **No Docker Compose** - Use tengil YAML specs instead
- **Proxmox 9.1+ required** - OCI support is new in Proxmox 9.1

## Migration from LXC

OCI containers are LXC containers with OCI metadata. Migration is straightforward:

1. Pull equivalent OCI image
2. Create new container with same mounts/config
3. Migrate data if needed
4. Test thoroughly
5. Remove old LXC container

## See Also

- [Proxmox OCI Support Documentation](https://pve.proxmox.com/wiki/OCI_Support)
- [OCI Image Spec](https://github.com/opencontainers/image-spec)
- [Docker Hub](https://hub.docker.com/)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
