# Changelog

All notable changes to Tengil will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - OCI Container Support (Phase 3 Complete)

**Major Features:**
- Native OCI container support for Proxmox 9.1+
- Auto-detection of OCI vs LXC containers in `tg apply`
- Support for Docker Hub, GitHub Container Registry (GHCR), Quay.io, and custom registries
- Expanded app catalog from 6 to 31+ popular self-hosted applications
- GPU passthrough support (Intel Quick Sync, NVIDIA NVENC, AMD VCE)
- ZFS mount integration for OCI containers
- Environment variable configuration

**CLI Commands:**
- `tg oci pull <image>:<tag>` - Pull OCI images
- `tg oci list [--format json]` - List cached OCI templates
- `tg oci login <registry>` - Authenticate to registries
- `tg oci logout <registry>` - Remove registry credentials

**App Catalog (31 apps):**
- **Media**: Jellyfin, Plex, Emby, Navidrome
- **Photos**: Immich, PhotoPrism, Photoview
- **Files**: Nextcloud, Seafile, FileBrowser
- **Automation**: Home Assistant, Mosquitto, Zigbee2MQTT
- **Documents**: Paperless-ngx, Calibre-web, BookStack, WikiJS
- **Passwords**: Vaultwarden, Passbolt
- **Monitoring**: Portainer, Uptime Kuma, Grafana, Prometheus
- **Network**: Pi-hole, AdGuard Home, Nginx, Traefik
- **Recipes**: Tandoor, Mealie
- **RSS**: FreshRSS, Miniflux

**Package Specs:**
- `jellyfin-oci.yml` - Media server with GPU transcoding
- `plex-oci.yml` - Plex media server
- `photoprism-oci.yml` - AI-powered photo management
- `vaultwarden-oci.yml` - Bitwarden-compatible password manager
- `paperless-ngx-oci.yml` - Document management with OCR
- `immich-oci.yml` - Self-hosted photo backup
- `nextcloud-oci.yml` - File sync and collaboration
- `homeassistant-oci.yml` - Home automation platform

**Testing:**
- 22 OCI-related tests (12 backend + 10 registry integration)
- 8 backend selection tests for auto-detection
- Production validated on Proxmox 9.1.1

**Documentation:**
- Comprehensive OCI Guide (`docs/OCI-GUIDE.md`)
- Updated README with OCI features
- Package spec examples with detailed configuration

### Fixed
- Registry URL detection for images with domain prefixes (e.g., `ghcr.io/owner/image`)
- Validator now accepts OCI containers without `template` field
- Mount point slot detection for OCI containers
- Features handling for OCI backend

### Changed
- `ContainerOrchestrator.create_container()` now auto-detects OCI vs LXC
- OCI backend improved with environment variable support
- Better error messages for OCI operations

## [0.9.0] - 2024-11-21

### Added
- Initial OCI backend implementation
- Skopeo integration for image pulling
- OCI template caching in `/var/lib/vz/template/cache`
- Support for custom registries

### Changed
- Refactored backend architecture for pluggable backends

## [0.8.0] - Previous Release

_(Previous changelog entries...)_

---

## Version Support

- **Proxmox 9.1+**: Full OCI support + all features
- **Proxmox 8.x**: All features except OCI containers
- **Proxmox 7.x**: Core ZFS and LXC features
