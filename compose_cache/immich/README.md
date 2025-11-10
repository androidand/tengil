# Immich - Self-Hosted Photo and Video Management

Curated Docker Compose configuration for Immich, a high-performance self-hosted photo and video backup solution.

## What This Provides

- **Photo/Video Management** - Modern Google Photos alternative
- **AI-Powered Search** - Face recognition, object detection, smart search
- **Mobile Apps** - iOS and Android with automatic backup
- **Machine Learning** - Local ML processing for facial recognition and CLIP search
- **Multi-User Support** - Separate libraries for family members
- **Hardware Acceleration** - GPU support for ML inference

## Architecture

Immich consists of 4 services:
1. **immich-server** - Main API and web interface
2. **immich-machine-learning** - AI/ML processing (face detection, CLIP embeddings)
3. **redis** - Job queue and caching
4. **database** - PostgreSQL with pgvector extension for ML embeddings

## Required Volumes

### Managed by Tengil:
- `/photos` → Photo/video library storage
- `/database` → PostgreSQL data

### Internal Docker volumes:
- `model-cache` → ML models (managed by Docker)

## Environment Variables

Create a `.env` file or pass via Tengil prompts:

```env
# Required: Database password
DB_PASSWORD=your-secure-password-here

# Optional: Database configuration
DB_USERNAME=immich
DB_DATABASE_NAME=immich

# Optional: Immich version
IMMICH_VERSION=release
```

## Storage Requirements

**Minimum:**
- 50GB for database and ML models
- Variable for photo/video storage (plan for growth)

**Recommended:**
- 100GB+ for database on fast storage (SSD/NVMe)
- 2TB+ for photo library (depends on your collection)
- ZFS recordsize=1M for photo storage (Tengil does this automatically)

## Hardware Acceleration

### Machine Learning (Recommended)

**NVIDIA GPU** (best performance):
```yaml
immich-machine-learning:
  runtime: nvidia
  image: ghcr.io/immich-app/immich-machine-learning:release-cuda
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - NVIDIA_DRIVER_CAPABILITIES=compute,video,utility
```

**Intel/AMD GPU** (OpenVINO):
```yaml
immich-machine-learning:
  devices:
    - /dev/dri:/dev/dri
  image: ghcr.io/immich-app/immich-machine-learning:release-openvino
```

GPU acceleration provides:
- 10-50x faster face detection
- 5-20x faster CLIP embedding generation
- Real-time processing for mobile uploads

## First-Time Setup

1. **Access Immich**: `http://your-proxmox-ip:2283`

2. **Create Admin Account**:
   - First user becomes admin
   - Use a strong password

3. **Configure Storage**:
   - Storage template: External library
   - Import path: `/data` (maps to your `/photos` dataset)

4. **Install Mobile Apps**:
   - iOS: App Store → "Immich"
   - Android: Play Store → "Immich"
   - Configure server URL: `http://your-proxmox-ip:2283`

5. **Enable Machine Learning**:
   - Settings → Machine Learning
   - Enable face detection
   - Enable CLIP search
   - Optionally enable GPU acceleration

6. **Run Initial Scan**:
   - Settings → Jobs
   - Run "Generate thumbnails" job
   - Run "Extract metadata" job
   - Run "Smart search" job (if enabled)

## Performance Tips

### Storage Optimization
- **Database**: Fast storage (SSD/NVMe) with ZFS recordsize=8K
- **Photos**: Large storage with ZFS recordsize=1M (Tengil default)
- **Separate pools**: Consider database on fast pool, photos on slow pool

### Memory Allocation
- **Minimum**: 4GB RAM for basic operation
- **Recommended**: 8GB+ RAM for ML processing
- **With GPU**: 6GB+ RAM + GPU memory

### Container Resources
```yaml
# Example deployment config in tengil.yml
containers:
  immich:
    memory: 8192  # 8GB RAM
    cores: 4      # 4 CPU cores
    template: debian-12-standard
```

## Security

⚠️ **Important Security Considerations:**

1. **Database Password**: Use a strong, unique password
2. **External Access**: Don't expose port 2283 without HTTPS
3. **Reverse Proxy**: Use Caddy/Traefik for SSL termination
4. **Backups**: Enable Immich's built-in backup or use Tengil ZFS snapshots
5. **Updates**: Keep Immich updated (security fixes are frequent)

### Reverse Proxy Example (Caddy)
```
photos.example.com {
    reverse_proxy immich_server:2283
}
```

## Mobile Backup

Immich provides automatic photo backup from mobile devices:

1. **Configure in mobile app**:
   - Settings → Backup
   - Choose albums to backup
   - Enable "Background backup"

2. **Choose backup settings**:
   - Original quality (recommended)
   - Skip duplicates
   - Archive originals after backup

3. **Battery optimization**:
   - iOS: Allow background refresh
   - Android: Disable battery optimization for Immich

## Troubleshooting

### Can't Upload Photos
- Check `/photos` volume is mounted and writable
- Verify UPLOAD_LOCATION=/data in environment
- Check container logs: `docker logs immich_server`

### Machine Learning Not Working
- Verify ML container is running: `docker ps | grep ml`
- Check model cache is populating: `docker volume inspect immich_model_cache`
- For GPU issues, verify Proxmox GPU passthrough

### Slow Face Detection
- Enable GPU acceleration (see Hardware Acceleration section)
- Increase container memory allocation
- Check CPU/GPU utilization during ML jobs

### Database Performance
- Ensure database is on fast storage (SSD)
- Increase shared_buffers in PostgreSQL
- Monitor with `docker stats immich_postgres`

### Mobile App Connection Issues
- Verify port 2283 is accessible
- Check firewall rules
- Use server's IP address (not localhost)
- Try HTTPS with reverse proxy if HTTP fails

## Updating

Immich updates frequently with new features and fixes.

**Manual update**:
```bash
cd /path/to/compose
docker-compose pull
docker-compose up -d
```

**With Tengil** (future):
```bash
tg upgrade immich
```

Always check [Immich Release Notes](https://github.com/immich-app/immich/releases) before updating.

## Backup Strategy

### Option 1: Immich Built-in Backup
- Admin → Backup
- Configure backup location
- Schedule automatic backups

### Option 2: ZFS Snapshots (Tengil)
```bash
# Snapshot photo library
zfs snapshot tank/photos@backup-$(date +%Y%m%d)

# Snapshot database
zfs snapshot tank/database@backup-$(date +%Y%m%d)
```

### Option 3: Rsync/Rclone
```bash
# Backup to remote storage
rclone sync /photos remote:immich-backup
```

## Migration from Google Photos

Immich provides a Google Takeout import tool:

1. Request Google Takeout (Photos only, JSON included)
2. Download archive
3. Use Immich CLI or upload via web interface
4. Import preserves metadata, albums, and timestamps

## Resource Usage

**Typical resource consumption:**

| Component | CPU | RAM | Storage |
|-----------|-----|-----|---------|
| immich-server | 1-2 cores | 2-4GB | Minimal |
| immich-ml | 2-4 cores | 2-4GB | ~5GB models |
| database | 1-2 cores | 1-2GB | Variable |
| redis | <0.5 cores | 256MB | Minimal |

**During ML processing** (face detection, CLIP):
- CPU: 50-100% on allocated cores
- GPU: 50-100% if enabled
- RAM: 4-8GB peak usage

## Advanced Configuration

### External Library

For existing photo libraries:

1. Mount external path to container
2. Add external library in Immich settings
3. Specify scan path
4. Run import job

### Multi-User Setup

1. Admin creates users
2. Each user gets separate library
3. Optional: Shared albums between users

### Custom ML Models

Advanced users can provide custom CLIP models:
- Download model to `model-cache` volume
- Configure in Immich settings
- Restart ML container

## Useful Links

- **Official Docs**: https://immich.app/docs
- **GitHub**: https://github.com/immich-app/immich
- **Discord**: https://discord.gg/immich (community support)
- **Release Notes**: https://github.com/immich-app/immich/releases

## Why Immich?

✅ **Truly self-hosted** - No cloud dependencies
✅ **Modern UX** - Beautiful, fast web and mobile apps
✅ **Privacy-focused** - Your photos never leave your server
✅ **Active development** - Weekly releases with new features
✅ **Open source** - AGPLv3 license
✅ **ML-powered** - Face recognition and smart search
✅ **Free** - No subscription fees or user limits
