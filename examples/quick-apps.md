# Deploy Apps with Tengil - Quick Examples

After the improvements we just made, deploying apps is now **dead simple**:

## 🚀 One-Command Docker Host

```bash
# Generate config
tg init --package docker-host

# Deploy everything
tg apply
```

**What you get:**
- ✅ LXC container created
- ✅ Docker installed
- ✅ Portainer running at http://container-ip:9000
- ✅ AppArmor auto-configured
- ✅ Ready to deploy any Docker app!

## 📦 Deploy Any App

### Example 1: Jellyfin Media Server

```yaml
pools:
  tank:
    datasets:
      media:
        profile: media
        containers:
          - name: jellyfin
            auto_create: true
            template: debian-12-standard
            mount: /media
            requires_docker: false  # Native install
            resources:
              memory: 4096
              cores: 4
              disk: 16G
            post_install:
              - tteck/jellyfin
```

Run `tg apply` → Jellyfin at http://ip:8096

### Example 2: Home Assistant

```yaml
pools:
  tank:
    datasets:
      homeassistant:
        profile: dev
        containers:
          - name: hass
            auto_create: true
            template: debian-12-standard
            mount: /config
            privileged: true
            resources:
              memory: 2048
              cores: 2
              disk: 16G
            post_install:
              - tteck/homeassistant
```

Run `tg apply` → Home Assistant at http://ip:8123

### Example 3: Nextcloud (Docker)

```yaml
pools:
  tank:
    datasets:
      nextcloud:
        profile: dev
        containers:
          - name: nextcloud
            auto_create: true
            template: debian-12-standard
            mount: /data
            privileged: true
            requires_docker: true  # Auto AppArmor
            resources:
              memory: 4096
              cores: 4
              disk: 32G
            post_install:
              - docker
              - |
                # Deploy Nextcloud via Docker Compose
                mkdir -p /data/nextcloud
                cat > /data/nextcloud/docker-compose.yml <<'EOF'
                version: '3'
                services:
                  nextcloud:
                    image: nextcloud:latest
                    restart: always
                    ports:
                      - "80:80"
                    volumes:
                      - /data/nextcloud/data:/var/www/html
                    environment:
                      - SQLITE_DATABASE=nextcloud
                EOF
                cd /data/nextcloud && docker compose up -d
```

Run `tg apply` → Nextcloud at http://ip

### Example 4: Pi-hole Ad Blocker

```yaml
pools:
  tank:
    datasets:
      pihole:
        profile: dev
        containers:
          - name: pihole
            auto_create: true
            template: debian-12-standard
            mount: /etc/pihole
            resources:
              memory: 1024
              cores: 1
              disk: 8G
            post_install:
              - tteck/pihole
```

Run `tg apply` → Pi-hole at http://ip/admin

## 🎯 Available tteck Scripts

Tengil includes shortcuts for popular apps via tteck scripts:

- `tteck/docker` - Docker Engine
- `tteck/portainer` - Portainer UI
- `tteck/jellyfin` - Jellyfin media server
- `tteck/homeassistant` - Home Assistant
- `tteck/nextcloud` - Nextcloud (native)
- `tteck/pihole` - Pi-hole
- `tteck/adguard` - AdGuard Home
- `tteck/wireguard` - WireGuard VPN
- `tteck/nginx-proxy-manager` - Nginx Proxy Manager
- `tteck/plex` - Plex Media Server
- `tteck/sonarr` - Sonarr
- `tteck/radarr` - Radarr
- `tteck/qbittorrent` - qBittorrent

## 🔧 Custom Commands

You can run any shell commands during post-install:

```yaml
post_install:
  - docker
  - |
    # Install custom app
    apt-get update
    apt-get install -y nginx
    systemctl enable nginx
    echo "Hello from Tengil" > /var/www/html/index.html
```

## ✨ Key Features

1. **Auto-create containers** - Set `auto_create: true`
2. **Automatic Docker setup** - Use `requires_docker: true`
3. **Mount ZFS datasets** - Automatic with `mount: /path`
4. **Post-install automation** - Apps installed during deployment
5. **IP address shown** - No guessing where to access services
6. **One command** - Just `tg apply`!

## 🎓 Workflow

1. Edit `tengil.yml` (add your app container)
2. Run `tg diff` (preview changes)
3. Run `tg apply` (deploy)
4. Access at displayed IP address
5. Commit config: `git commit -am "Added jellyfin"`

## 💡 Pro Tips

- Use `profile: media` for video files (no compression)
- Use `profile: dev` for general apps (compression + fast I/O)
- Set `privileged: true` for Docker containers
- Set `requires_docker: true` to auto-configure AppArmor
- Combine multiple apps in one dataset with multiple containers
- Use `startup_order` to control boot sequence

## 🆘 Troubleshooting

**Container won't start?**
```bash
tg logs
pct status 100
```

**Docker permission denied?**
- Make sure `privileged: true` and `requires_docker: true` are set

**Can't access service?**
- Check container IP: `pct exec 100 -- hostname -I`
- Check firewall on Proxmox host
- Verify service is running: `pct exec 100 -- systemctl status docker`

**Need more resources?**
- Edit `tengil.yml` and increase memory/cores
- Run `tg apply` (updates existing container)
