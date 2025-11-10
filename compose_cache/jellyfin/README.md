# Jellyfin Media Server

Curated Docker Compose configuration for Jellyfin media server.

## What This Provides

- **Jellyfin server** - Open-source media system (Plex alternative)
- **Multi-library support** - Movies, TV shows, music, photos
- **Hardware transcoding** - Intel QuickSync / NVIDIA support (optional)
- **DLNA/Auto-discovery** - Easily found by client devices

## Configuration Notes

### Network Mode
This compose uses **bridge mode** for better security and isolation. Host mode is often recommended for DLNA, but bridge with explicit port mappings works fine.

### Media Mounts
All media volumes are mounted **read-only** (`:ro` flag). This prevents accidental deletion from Jellyfin UI. Jellyfin only needs read access to stream media.

To add/remove media, use the SMB shares created by Tengil.

### Hardware Transcoding

**Intel QuickSync** (integrated GPUs):
```yaml
devices:
  - /dev/dri:/dev/dri
```

**NVIDIA GPU**:
```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=compute,video,utility
```

Both require Proxmox GPU passthrough configuration.

## First-Time Setup

1. Access Jellyfin: `http://your-proxmox-ip:8096`
2. Create admin account
3. Add media libraries:
   - Movies → `/media`
   - TV Shows → `/tv`
   - Music → `/music` (if applicable)
   - Photos → `/photos` (if applicable)
4. Enable hardware transcoding:
   - Dashboard → Playback → Hardware acceleration
   - Select Intel QuickSync or NVIDIA NVENC

## Security

⚠️ **Important:**
- Set up authentication immediately
- Don't expose port 8096 to the internet without HTTPS
- Use a reverse proxy (Caddy/Traefik) for external access
- Read-only mounts prevent media manipulation

## Updating

Jellyfin updates automatically with `docker-compose pull && docker-compose up -d`.

## Troubleshooting

**Can't find media:**
- Check that volumes are mounted correctly
- Verify file permissions (Jellyfin runs as PUID/PGID 1000)
- Check ZFS dataset is mounted to container

**No hardware transcoding:**
- Verify GPU passthrough in Proxmox
- Check device permissions in container
- Enable in Jellyfin Dashboard → Playback

**DLNA not working:**
- Check firewall allows UDP 1900 and 7359
- Verify clients are on same network
- Try enabling UPnP in router

## Performance Tips

- Store `/config` and `/cache` on fast storage (SSD)
- Use ZFS recordsize=1M for media datasets (Tengil does this)
- Enable hardware transcoding for 4K content
- Allocate at least 4GB RAM for Jellyfin container
