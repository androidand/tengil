# Changelog

All notable changes to Tengil will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - OCI Container Support (Experimental / Tech Preview)

**Features implemented (experimental):**
- OCI backend (skopeo + pct) with create-time env var support
- Basic auto-detection in orchestrator when spec has `type: oci` or an `oci` section
- Static OCI catalog helpers (`tg oci catalog/search/install/status`)
- GPU passthrough and ZFS mount support (same as LXC flow)

**Not implemented / not shipped:**
- No `tg oci pull/list/login/logout` commands
- No automated registry integration (static catalog only)
- No package specs for OCI apps beyond existing examples
- No production validation; tests are mocked only
- Update workflow still requires recreate + volume reuse

**Testing:**
- Mocked unit/integration tests for OCI backend command generation
- Backend selection tests (mocked) for OCI vs LXC

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
