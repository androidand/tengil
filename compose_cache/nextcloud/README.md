# Nextcloud All-in-One

Curated Docker Compose configuration for Nextcloud AIO (All-in-One), the easiest way to deploy a fully-featured Nextcloud instance.

## What This Provides

- **File Sync & Share** - Dropbox/Google Drive alternative
- **Collaboration Suite** - Office documents, calendars, contacts
- **Talk** - Video conferencing and chat
- **Photos** - Photo backup and management
- **Mail** - Webmail client
- **Full Office Suite** - Collabora Online (LibreOffice)
- **Backup System** - Built-in Borg backup solution

## What is All-in-One (AIO)?

Nextcloud AIO is a **mastercontainer** that manages multiple sub-containers:
- Nextcloud server
- PostgreSQL database
- Redis cache
- Collabora Office
- Nextcloud Talk
- Imaginary (image processing)
- Fulltextsearch
- Backup container (Borg)

The mastercontainer handles updates, backups, and configuration automatically.

## Architecture

Unlike traditional compose files, AIO uses a **single mastercontainer** that:
1. Manages Docker containers on the host via socket mount
2. Deploys additional containers as needed
3. Handles updates and backups automatically
4. Provides a web interface for configuration

**Important**: This means the mastercontainer will create additional containers on your host that aren't defined in this compose file.

## Required Volumes

### Managed by Docker:
- `nextcloud_aio_mastercontainer` - AIO config (must have exact name)

### Managed by Tengil:
- `/data` - Nextcloud user data (photos, documents, files)
  - Set via `NEXTCLOUD_DATADIR=/data` environment variable
  - ⚠️ **Cannot be changed after first install!**

### Created by AIO automatically:
The mastercontainer will create additional volumes for:
- PostgreSQL database
- Redis cache
- Nextcloud config
- Collabora data
- etc.

## Critical Setup Notes

### ⚠️ Data Directory Warning

The `NEXTCLOUD_DATADIR` must be set **BEFORE** first installation and **cannot be changed** afterward without reinstalling Nextcloud.

```yaml
environment:
  - NEXTCLOUD_DATADIR=/data
```

Tengil will set this to a ZFS dataset automatically.

### ⚠️ Volume Name Restriction

The volume name `nextcloud_aio_mastercontainer` **must NOT be changed**. The AIO backup system requires this exact name.

## First-Time Setup

### 1. Start the Mastercontainer

```bash
docker-compose up -d
```

### 2. Access AIO Interface

Open: `https://your-proxmox-ip:8080`

You'll see a self-signed SSL warning - this is expected. Accept it to continue.

### 3. Initial Configuration

The AIO interface will show:
- A generated admin password (save this!)
- Configuration wizard

**Configure**:
1. **Domain**: Enter your domain or IP address
2. **Timezone**: Select your timezone
3. **Optional containers**: Choose what to enable
   - Collabora Office (recommended)
   - Talk (video chat)
   - Imaginary (image preview)
   - Fulltextsearch
4. **Start containers**: Click to deploy

### 4. Wait for Deployment

AIO will:
- Pull container images (~2-5GB total)
- Create volumes
- Initialize database
- Configure Nextcloud

This takes 5-15 minutes depending on network speed.

### 5. Access Nextcloud

After deployment completes:
- Web interface: `https://your-proxmox-ip` or `https://your-domain`
- Login with credentials shown in AIO interface

## Reverse Proxy Setup

For production use with a domain name, configure a reverse proxy:

### Option 1: External Reverse Proxy (Recommended)

If you have Caddy/Nginx/Traefik on another system:

1. Update compose environment:
```yaml
environment:
  - APACHE_PORT=11000
  - APACHE_IP_BINDING=127.0.0.1  # If proxy on same host
```

2. Remove port 80 and 8443 from compose:
```yaml
ports:
  - "8080:8080"  # Keep only AIO interface
```

3. Configure reverse proxy to forward to port 11000

**Caddy example**:
```
cloud.example.com {
    reverse_proxy nextcloud:11000
}
```

### Option 2: Tailscale (No Domain Required)

See: https://github.com/nextcloud/all-in-one/discussions/6817

### Option 3: Built-in Caddy

AIO includes a Caddy config (commented out in compose file).

## Storage Configuration

### Optimal ZFS Settings (Tengil handles this):

```yaml
# In tengil.yml
pools:
  tank:
    datasets:
      nextcloud-data:
        profile: dev          # 128K recordsize for mixed files
        consumers:
          - type: container
            name: nextcloud
            mount: /data
```

### Storage Growth Planning

**Typical usage per user**:
- Light user: 5-20GB
- Medium user: 50-200GB
- Heavy user (photo backup): 500GB+

**Nextcloud overhead**:
- Database: 1-10GB
- Redis/cache: 1-5GB
- Collabora: 2-5GB
- Preview thumbnails: 10-50GB

**Recommended**:
- Start with 500GB for `/data`
- Monitor usage and expand as needed
- ZFS makes expansion easy

## Hardware Acceleration

### Preview Generation (Recommended)

Nextcloud generates thumbnails for photos and videos.

**Intel QuickSync**:
```yaml
devices:
  - /dev/dri:/dev/dri
environment:
  - NEXTCLOUD_ENABLE_DRI_DEVICE=true
```

**NVIDIA GPU**:
```yaml
runtime: nvidia
environment:
  - NEXTCLOUD_ENABLE_NVIDIA_GPU=true
  - NVIDIA_VISIBLE_DEVICES=all
  - NVIDIA_DRIVER_CAPABILITIES=compute,video,utility
```

Benefits:
- 5-10x faster thumbnail generation
- Lower CPU usage
- Faster photo gallery loading

## Performance Tuning

### Memory Allocation

**Minimum**: 4GB RAM
**Recommended**: 8-16GB RAM

In tengil.yml:
```yaml
containers:
  nextcloud:
    memory: 8192    # 8GB
    cores: 4
```

### Upload Limits

Default is 512MB. Increase for large files:

```yaml
environment:
  - NEXTCLOUD_UPLOAD_LIMIT=16G
  - NEXTCLOUD_MAX_TIME=3600
  - NEXTCLOUD_MEMORY_LIMIT=512M
```

### Database Performance

AIO automatically tunes PostgreSQL, but ensure:
- Database is on fast storage (SSD)
- At least 2GB RAM allocated to database
- Regular maintenance (AIO handles this)

## Backup Strategy

### Option 1: AIO Built-in Backup (Recommended)

AIO includes Borg backup:

1. Access AIO interface: `https://your-ip:8080`
2. Navigate to Backup section
3. Configure:
   - Backup location (external storage)
   - Backup schedule
   - Retention policy

**Default retention**:
```bash
--keep-within=7d --keep-weekly=4 --keep-monthly=6
```

**Custom retention**:
```yaml
environment:
  - BORG_RETENTION_POLICY=--keep-daily=7 --keep-weekly=4 --keep-monthly=12
```

### Option 2: ZFS Snapshots (Tengil)

```bash
# Snapshot data directory
zfs snapshot tank/nextcloud-data@backup-$(date +%Y%m%d)

# List snapshots
zfs list -t snapshot | grep nextcloud
```

### Option 3: Rsync/Rclone

```bash
# Backup to remote storage
rclone sync /data remote:nextcloud-backup --exclude 'cache/**'
```

## Updating

AIO automatically notifies when updates are available.

**Update process**:
1. Access AIO interface: `https://your-ip:8080`
2. Click "Update" button
3. AIO will:
   - Stop containers
   - Pull new images
   - Update Nextcloud
   - Restart containers

**Automatic updates**: Can be enabled in AIO settings.

## Security

### ⚠️ Important Security Considerations

1. **HTTPS Required**: Never expose Nextcloud over HTTP to internet
2. **Strong Passwords**: Enable 2FA for admin account
3. **Reverse Proxy**: Use for external access
4. **Firewall**: Only expose necessary ports
5. **Backups**: Test backup restoration regularly
6. **Updates**: Keep Nextcloud updated (security is critical)

### Recommended Security Setup

1. **Enable 2FA**:
   - Install "Two-Factor TOTP Provider" app
   - Require for admin accounts

2. **Use Reverse Proxy**:
   - Don't expose port 80/8443 directly
   - Use Caddy/Traefik with automatic HTTPS

3. **Brute Force Protection**:
   - Built-in to Nextcloud
   - Automatically enabled

4. **File Access Control**:
   - Set appropriate sharing permissions
   - Review external shares regularly

## Mobile & Desktop Apps

### Mobile Apps
- **Android**: Play Store → "Nextcloud"
- **iOS**: App Store → "Nextcloud"
- Configure: Enter server URL and login

Features:
- Automatic photo backup
- Offline file access
- Share files from other apps
- Calendar/contact sync

### Desktop Apps
- **Windows/Mac/Linux**: https://nextcloud.com/install/#install-clients

Features:
- Sync folders
- File locking
- Selective sync
- System tray integration

### Sync Configuration

**Recommended sync settings**:
- Enable "Ask for confirmation before synchronizing folders"
- Use selective sync for large folders
- Enable virtual files (Windows 10+)

## Troubleshooting

### Can't Access AIO Interface
- Check port 8080 is open
- Verify container is running: `docker ps | grep nextcloud`
- Check firewall rules
- Try: `https://server-ip:8080` (note HTTPS)

### Self-Signed Certificate Warning
- This is expected for the AIO interface
- Accept the certificate to continue
- Production Nextcloud should use proper SSL via reverse proxy

### Can't Upload Files
- Check NEXTCLOUD_DATADIR is set correctly
- Verify volume is mounted: `docker inspect nextcloud-aio-mastercontainer`
- Check disk space: `df -h`
- Verify permissions on /data directory

### Slow Performance
- Check available RAM: `docker stats`
- Verify database is on fast storage (SSD)
- Enable hardware acceleration for preview generation
- Increase PHP memory limit if needed

### Database Connection Errors
- AIO manages database automatically
- If errors persist, check AIO logs: `docker logs nextcloud-aio-mastercontainer`
- Restart mastercontainer: `docker-compose restart`

### Backup Fails
- Verify backup location has enough space
- Check Borg logs in AIO interface
- Ensure volume name is exactly `nextcloud_aio_mastercontainer`

## Advanced Configuration

### External Storage

Nextcloud can mount external storage:
- SMB/CIFS shares
- S3 buckets
- FTP/SFTP
- WebDAV

Configure in: Settings → Administration → External storage

### LDAP/Active Directory

For enterprise user management:
1. Install "LDAP user and group backend" app
2. Configure: Settings → LDAP/AD integration
3. Test connection and import users

### Custom Apps

Install additional apps:
- Admin → Apps
- Browse featured/recommended apps
- Popular: Memories, Recognize, Music, Deck, Notes

### Office Suite Alternatives

Default is Collabora. Alternatives:
- OnlyOffice (lighter weight)
- Microsoft Office Online (requires Microsoft 365)

## Resource Usage

**Typical consumption (5 users)**:

| Component | CPU | RAM | Storage |
|-----------|-----|-----|---------|
| Nextcloud | 1-2 cores | 1-3GB | Variable |
| PostgreSQL | 0.5-1 core | 1-2GB | 1-10GB |
| Redis | <0.5 cores | 512MB | Minimal |
| Collabora | 1-2 cores | 2-4GB | 2-5GB |
| Total | 3-5 cores | 5-10GB | Variable |

**Scale**:
- 50 users: 8-16GB RAM, 4-8 cores
- 500 users: 32-64GB RAM, 16-32 cores

## Migration

### From Other Clouds

**Google Drive**:
1. Export data via Google Takeout
2. Upload to Nextcloud
3. Enable "External storage" for gradual migration

**Dropbox**:
1. Download all files
2. Use desktop client to sync to Nextcloud
3. Verify sync before deleting Dropbox

**OneDrive**:
- Similar process to Google Drive
- Use desktop client for large libraries

### From Previous Nextcloud

AIO provides migration tool:
- Backup old instance
- Import into AIO
- See: https://github.com/nextcloud/all-in-one#migration

## Useful Links

- **Official Docs**: https://docs.nextcloud.com
- **AIO GitHub**: https://github.com/nextcloud/all-in-one
- **AIO Docs**: https://github.com/nextcloud/all-in-one#readme
- **Community Forum**: https://help.nextcloud.com
- **Apps Store**: https://apps.nextcloud.com

## Why Nextcloud AIO?

✅ **Complete Solution** - Everything included (office, talk, backup)
✅ **Easy Setup** - One mastercontainer manages everything
✅ **Automatic Updates** - No manual maintenance
✅ **Built-in Backup** - Borg backup included
✅ **Well Tested** - Official Nextcloud deployment method
✅ **Active Support** - Regular updates and community
✅ **Production Ready** - Used by thousands of installations
✅ **Open Source** - AGPLv3 license

## Why Self-Host Nextcloud?

✅ **Privacy** - Your data stays on your server
✅ **Control** - Full ownership and customization
✅ **Cost** - No subscription fees (vs Dropbox $20/mo)
✅ **Unlimited** - Storage limited only by your disks
✅ **Integration** - CalDAV, CardDAV, WebDAV support
✅ **Compliance** - Meet data residency requirements
✅ **Features** - Office suite, video calls, photo management
