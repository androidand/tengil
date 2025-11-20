# Deploy All Apps - Complete Media Server Stack

## 🎯 What We're Deploying

1. **Jellyfin** - Media server with GPU transcoding
2. **Immich** - Google Photos alternative with ML
3. **Syncthing** - File sync (Dropbox replacement)
4. **Home Assistant MCP** - AI control for smart home

## 📋 Prerequisites

- Proxmox server running (192.168.1.42)
- Tengil installed via pipx
- ZFS pool named `tank`
- Internet connection for downloading packages

## 🚀 Quick Deploy (All at Once)

Create one config file with all 4 apps:

```bash
cd /root  # Or your preferred location
nano tengil.yml
```

Paste this complete configuration:

```yaml
pools:
  tank:
    datasets:
      # Jellyfin - Media Server
      media:
        profile: media  # No compression for video
        quota: 500G
        containers:
          - name: jellyfin
            auto_create: true
            template: debian-12-standard
            mount: /media
            privileged: true
            gpu:
              passthrough: true
              type: auto
            resources:
              memory: 4096
              cores: 4
              disk: 16G
            startup_order: 200
            post_install:
              - tteck/jellyfin
      
      # Immich - Photo Backup
      photos:
        profile: dev  # Compression enabled
        quota: 500G
        containers:
          - name: immich
            auto_create: true
            template: debian-12-standard
            mount: /data
            privileged: true
            requires_docker: true
            gpu:
              passthrough: true
              type: auto
            resources:
              memory: 8192
              cores: 4
              disk: 32G
            startup_order: 150
            post_install:
              - docker
              - |
                cd /data
                wget -O docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
                wget -O .env https://github.com/immich-app/immich/releases/latest/download/example.env
                mkdir -p /data/library
                docker compose up -d
                echo "Immich starting at http://$(hostname -I | awk '{print $1}'):2283"
      
      # Syncthing - File Sync
      sync:
        profile: dev
        quota: 100G
        containers:
          - name: syncthing
            auto_create: true
            template: debian-12-standard
            mount: /sync
            resources:
              memory: 2048
              cores: 2
              disk: 8G
            startup_order: 100
            post_install:
              - |
                apt-get update && apt-get install -y curl apt-transport-https
                curl -s https://syncthing.net/release-key.txt | gpg --dearmor | tee /usr/share/keyrings/syncthing-archive-keyring.gpg >/dev/null
                echo "deb [signed-by=/usr/share/keyrings/syncthing-archive-keyring.gpg] https://apt.syncthing.net/ syncthing stable" | tee /etc/apt/sources.list.d/syncthing.list
                apt-get update && apt-get install -y syncthing
                systemctl enable syncthing@root.service
                systemctl start syncthing@root.service
                sleep 3
                sed -i 's|<address>127.0.0.1:8384</address>|<address>0.0.0.0:8384</address>|' /root/.config/syncthing/config.xml
                systemctl restart syncthing@root.service
                mkdir -p /sync/{Documents,Photos}
                echo "Syncthing at http://$(hostname -I | awk '{print $1}'):8384"
        shares:
          smb:
            name: Syncthing
            comment: Synced files
            browseable: yes
```

## 📦 Deploy

```bash
# Preview changes
tengil diff

# Deploy everything
tengil apply -y
```

This will:
1. Create 4 datasets with proper profiles
2. Create 4 LXC containers
3. Configure GPU passthrough for Jellyfin and Immich
4. Install all applications
5. Show access URLs

## ⏱️ Timeline

- **Jellyfin**: ~5 minutes
- **Immich**: ~10 minutes (Docker images)
- **Syncthing**: ~3 minutes
- **Total**: ~20 minutes

## 🔍 Monitor Progress

Open another terminal and watch:

```bash
# Watch container creation
watch -n 2 'pct list'

# Follow logs
tengil apply -v
```

## ✅ Verify Deployment

After completion, list all running apps:

```bash
tengil apps list
```

You'll see output like:

```
Running Applications
┌─────────────┬──────────────┬─────────────────┬──────────────────────────┐
│ Container   │ Service      │ Description     │ Access URL               │
├─────────────┼──────────────┼─────────────────┼──────────────────────────┤
│ jellyfin    │ Jellyfin     │ Media server    │ http://192.168.1.150:8096│
│ immich      │ Immich       │ Photo backup    │ http://192.168.1.151:2283│
│ syncthing   │ Syncthing    │ File sync       │ http://192.168.1.152:8384│
└─────────────┴──────────────┴─────────────────┴──────────────────────────┘
```

## 🎬 Post-Deployment Setup

### Jellyfin

1. Open http://container-ip:8096
2. Complete setup wizard
3. Add media libraries → `/media`
4. Enable GPU transcoding:
   - Dashboard → Playback → Hardware acceleration
   - Select "Intel QuickSync" or "AMD AMF"

### Immich

1. Open http://container-ip:2283
2. Create admin account
3. Install mobile app
4. Connect to server and enable backup

### Syncthing

1. Open http://container-ip:8384
2. Add remote devices (phones, computers)
3. Create folders to sync
4. Install Syncthing on other devices

## 📱 Access from Anywhere

Copy-paste friendly URL list:

```bash
tengil apps list --format urls
```

## 🔧 Troubleshooting

**GPU not detected:**
```bash
# Check from host
lspci | grep VGA

# Check in container
pct exec <vmid> -- ls -l /dev/dri
```

**Service not running:**
```bash
# Check container status
pct status <vmid>

# View logs
pct exec <vmid> -- journalctl -xe
```

**Can't access web UI:**
```bash
# Get container IP
pct exec <vmid> -- hostname -I

# Check port is listening
pct exec <vmid> -- netstat -tlnp | grep <port>
```

## 🎓 Next Steps

1. Add media files to Jellyfin
2. Set up phone backup to Immich
3. Configure Syncthing on computers
4. Explore `tengil apps` commands
5. Set up automated backups

## 🌟 Pro Tips

- Use `tengil container exec jellyfin <command>` for quick commands
- Use `tengil apps open jellyfin` to open in browser
- All configs saved in `tengil.yml` - version control it!
- GPU transcoding saves CPU and enables more streams
- Immich ML processing will take hours for initial scan

Enjoy your complete media and productivity stack! 🎉
