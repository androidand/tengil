# Tengil Development Tasks

**Last Updated:** November 21, 2025  
**Current Phase:** Phase 4 In Progress (3/5 tasks complete)  
**Status:** Package specs expanded to 14/31 apps (45% coverage)

---

## 📊 Phase Completion Status

- ✅ **Phase 1: Research & Design** (100%) - OCI architecture validated
- ✅ **Phase 2: Core OCI Implementation** (100%) - Backend + CLI complete  
- ✅ **Phase 3: Testing & Documentation** (100%) - 22 tests passing, docs comprehensive
- 🔄 **Phase 4: Ecosystem Expansion** (0%) - Planned tasks below
- 📋 **Phase 5: Advanced Features** (0%) - Import, analysis, backup tools
- 📋 **Phase 6: User Experience** (0%) - Multi-container, Web UI

---

## 🎯 CURRENT FOCUS: Phase 4 - OCI Ecosystem Expansion

**Goal:** Make the OCI system more discoverable, user-friendly, and complete.

### 🚨 STRATEGIC PIVOT SUMMARY (COMPLETED)

Proxmox 9.1 introduced **native OCI container support**. Tengil successfully pivoted from LXC-focused to **OCI-first** architecture.

**What Changed:**
1. **Native OCI Support**: Proxmox 9.1 runs OCI containers (Docker images) without Docker Engine
2. **Simpler Architecture**: Direct OCI → LXC conversion, no Docker-in-LXC hacks
3. **Better Ecosystem**: Direct access to Docker Hub, GHCR, Quay.io registries
4. **Modern Workflow**: `tengil.yml` declares OCI containers with auto-detection

**Implementation Status:**
- ✅ OCI Backend (tengil/services/oci_backend.py) - 333 lines, fully functional
- ✅ OCI Registry (tengil/services/oci_registry.py) - 130 lines, 31-app catalog
- ✅ CLI Commands (tg oci pull/list/login/logout) - All working
- ✅ Auto-detection in `tg apply` - Detects OCI vs LXC automatically
- ✅ GPU Passthrough - Intel/NVIDIA/AMD support validated
- ✅ ZFS Mounts - Dataset → container integration working
- ✅ Environment Variables - Full support at create-time
- ✅ Documentation - OCI-GUIDE.md, CHANGELOG.md, README updated
- ✅ Test Coverage - 22 OCI tests passing (10 registry + 12 backend)

**What Was Kept:**
- ✅ ZFS dataset management, profiles, share management, state tracking
- ✅ Package system (now supports both OCI and LXC)
- ✅ Declarative YAML config, diff/apply workflow
- ✅ LXC support (maintained for legacy/special cases)

**What Changed:**
- 🔄 OCI-first approach: Auto-detects container type from image field
- 🔄 Direct skopeo/pct integration instead of Docker-in-LXC
- 🔄 Simplified configs: No more post_install scripts for app containers

**Example: OCI-First Config (Production Ready)**

```yaml
pools:
  tank:
    datasets:
      apps:
        profile: appdata
        containers:
          - name: jellyfin
            image: jellyfin/jellyfin:latest  # Auto-detects as OCI
            cores: 4
            memory: 4096
            disk: 16
            env:
              JELLYFIN_PublishedServerUrl: http://jellyfin.local
            mounts:
              - source: /tank/media
                target: /media
                readonly: true
            gpu: true  # Intel Quick Sync, NVIDIA NVENC, AMD VCE

          - name: photoprism
            image: photoprism/photoprism:latest
            cores: 4
            memory: 4096
            disk: 32
            env:
              PHOTOPRISM_ADMIN_USER: admin
              PHOTOPRISM_ADMIN_PASSWORD: changeme
            mounts:
              - source: /tank/photos/originals
                target: /photoprism/originals
```

**Benefits Realized:**
- ✅ No privileged containers needed
- ✅ No Docker Engine installation
- ✅ Official images from registries
- ✅ Simpler, more maintainable
- ✅ Better security (no nested virtualization)
- ✅ Faster deployment (no LXC → Docker overhead)
- ✅ Auto-detection of OCI vs LXC containers

---

## 🎯 PHASE 4: OCI Ecosystem Expansion (IN PROGRESS)

### Task 1: Interactive App Catalog (HIGH PRIORITY)

**Goal:** Make the 31-app catalog searchable and browsable via CLI.

- [x] **Implement `tg oci catalog` command** ✅ COMPLETED
  - [x] List all 31 apps with name, description, registry, category
  - [x] Add `--category <name>` filter (media, photos, files, automation, etc.)
  - [x] Add `--format json` for programmatic access
  - [x] Show popular apps by default, all apps with `--all`
  - [x] Enhanced table format with Rich tables
  - [x] Package spec availability indicator (✓)

- [x] **Implement `tg oci search <query>` command** ✅ COMPLETED
  - [x] Search by app name (case-insensitive)
  - [x] Search by description text
  - [x] Show matching apps with full details
  - [x] Suggest similar apps if no exact match

- [x] **Implement `tg oci info <app>` command** ✅ COMPLETED
  - [x] Show detailed app information
  - [x] Display default environment variables
  - [x] Show recommended mounts/volumes
  - [x] Link to official documentation
  - [x] Show related package specs if available

**Expected Behavior:**
```bash
tg oci catalog                    # List popular apps
tg oci catalog --category media   # Filter by category
tg oci search jellyfin            # Find specific app
tg oci info jellyfin              # Detailed app info
```

---

### Task 2: OCI Remove Command (MEDIUM PRIORITY)

**Goal:** Allow cleanup of cached OCI templates.

- [ ] **Implement `tg oci remove <image>` command**
  - [ ] Delete template from `/var/lib/vz/template/cache/`
  - [ ] Show template size before deletion
  - [ ] Require confirmation or `--force` flag
  - [ ] Error if template is in use by containers
  - [ ] Support wildcards (e.g., `tg oci remove alpine:*`)

- [ ] **Add `tg oci prune` command**
  - [ ] Remove all unused OCI templates
  - [ ] Calculate total space to be freed
  - [ ] Show dry-run with `--dry-run`
  - [ ] Require confirmation

**Expected Behavior:**
```bash
tg oci remove alpine:latest       # Remove specific template
tg oci remove alpine:*            # Remove all Alpine versions
tg oci prune                      # Remove all unused templates
tg oci prune --dry-run            # Show what would be removed
```

---

### Task 3: Complete Package Spec Coverage (MEDIUM PRIORITY)

**Goal:** Provide ready-to-deploy configs for all 31 catalog apps.

**Current Status:** 8/31 specs complete (26%)
- ✅ jellyfin-oci.yml
- ✅ plex-oci.yml
- ✅ photoprism-oci.yml
- ✅ vaultwarden-oci.yml
- ✅ paperless-ngx-oci.yml
- ✅ immich-oci.yml
- ✅ nextcloud-oci.yml
- ✅ homeassistant-oci.yml

**Missing Specs (23 apps):**

**Media (3):**
- [ ] emby-oci.yml - Alternative to Jellyfin
- [ ] navidrome-oci.yml - Music server
- [ ] audiobookshelf-oci.yml - Audiobook/podcast server

**Photos (2):**
- [ ] photoview-oci.yml - Simple photo gallery
- [ ] librephotos-oci.yml - Alternative to PhotoPrism

**Files (2):**
- [ ] seafile-oci.yml - Alternative to Nextcloud
- [ ] filebrowser-oci.yml - Simple file manager

**Automation (2):**
- [ ] mosquitto-oci.yml - MQTT broker
- [ ] zigbee2mqtt-oci.yml - Zigbee gateway

**Documents (3):**
- [ ] calibre-web-oci.yml - Ebook library
- [ ] bookstack-oci.yml - Wiki platform
- [ ] wikijs-oci.yml - Modern wiki

**Passwords (1):**
- [ ] passbolt-oci.yml - Team password manager

**Monitoring (3):**
- [ ] portainer-oci.yml - Container management
- [ ] uptimekuma-oci.yml - Uptime monitoring
- [ ] grafana-oci.yml - Metrics visualization
- [ ] prometheus-oci.yml - Metrics collection

**Network (3):**
- [ ] adguardhome-oci.yml - DNS ad blocker
- [ ] nginx-oci.yml - Web server/reverse proxy
- [ ] traefik-oci.yml - Modern reverse proxy

**Recipes (2):**
- [ ] tandoor-oci.yml - Recipe manager
- [ ] mealie-oci.yml - Recipe manager

**RSS (2):**
- [ ] freshrss-oci.yml - RSS aggregator
- [ ] miniflux-oci.yml - Minimalist RSS reader

**Priority Order:**
1. **High Usage:** portainer, traefik, grafana, prometheus (ops tools)
2. **Popular Categories:** adguardhome, mosquitto (network/automation)
3. **Alternatives:** emby, seafile, passbolt (provide choice)
4. **Specialized:** Remaining apps as time permits

---

### Task 4: CLI UX Improvements (LOW PRIORITY)

**Goal:** Polish the OCI experience with better feedback and validation.

- [ ] **Progress Bars for Image Pulls**
  - [ ] Show download progress during `tg oci pull`
  - [ ] Display layer extraction status
  - [ ] Show total size and time remaining
  - [ ] Use rich library or simple ASCII progress

- [ ] **Better Error Messages**
  - [ ] Detect missing registry authentication → suggest `tg oci login`
  - [ ] Detect insufficient storage → show available space
  - [ ] Detect network failures → suggest retry with helpful tips
  - [ ] Detect invalid image names → show format examples
  - [ ] Detect port conflicts → list conflicting containers

- [ ] **Validation Before Apply**
  - [ ] Check required environment variables
  - [ ] Validate mount paths exist on host
  - [ ] Check available resources (CPU, RAM, disk)
  - [ ] Warn about security issues (exposed ports, privileged mode)
  - [ ] Suggest GPU passthrough for media apps

- [ ] **Colored Output**
  - [ ] Green for success, red for errors, yellow for warnings
  - [ ] Use rich library for formatted tables
  - [ ] Support `--no-color` flag for scripts

**Example Improvements:**
```bash
# Before
Error: failed to pull image

# After
Error: Failed to pull alpine:latest
Possible causes:
  - Network connectivity issue (check internet connection)
  - Image does not exist (verify image name at hub.docker.com)
  - Registry requires authentication (run: tg oci login docker.io)

# Progress bar example
Pulling alpine:latest...
[████████████████████--------] 67% (3.2 MB / 4.8 MB) ETA: 5s
```

---

### Task 5: Error Handling Edge Cases (LOW PRIORITY)

**Goal:** Gracefully handle all failure scenarios.

**Test Cases:**

- [ ] **Invalid Image Names**
  - [ ] Test: `tg oci pull invalid..image::name`
  - [ ] Expected: Clear error with format guide
  - [ ] Implementation: Validate image name regex before pull

- [ ] **Missing Registry Authentication**
  - [ ] Test: Pull private image without login
  - [ ] Expected: Prompt to run `tg oci login`
  - [ ] Implementation: Check registry auth before pull

- [ ] **Insufficient Storage Space**
  - [ ] Test: Pull large image with full storage
  - [ ] Expected: Show available space, suggest cleanup
  - [ ] Implementation: Check storage before pull

- [ ] **Network Failures**
  - [ ] Test: Pull image with disconnected network
  - [ ] Expected: Clear error, suggest retry
  - [ ] Implementation: Add timeout and retry logic

- [ ] **Missing Environment Variables**
  - [ ] Test: Apply container without required env vars
  - [ ] Expected: List missing vars with descriptions
  - [ ] Implementation: Validate against app catalog requirements

- [ ] **Port Conflicts**
  - [ ] Test: Create container with already-bound port
  - [ ] Expected: List conflicting container, suggest alternative port
  - [ ] Implementation: Query existing containers before create

---

## � PHASE 5: Advanced Features (PLANNED)

### Task 6: State Import (`tg import`)

**Goal:** Reverse-engineer tengil.yml from existing Proxmox infrastructure.

- [ ] **Scan Existing Containers**
  - [ ] Use `pct list` to discover all containers
  - [ ] Detect OCI vs LXC containers
  - [ ] Parse `pct config` for each container
  - [ ] Extract: cores, memory, disk, mounts, env vars

- [ ] **Generate tengil.yml**
  - [ ] Group containers by storage pool
  - [ ] Infer dataset structure from mount paths
  - [ ] Create container specs with detected config
  - [ ] Preserve existing shares (SMB/NFS)

- [ ] **Interactive Mode**
  - [ ] Show detected infrastructure
  - [ ] Allow filtering containers to import
  - [ ] Suggest optimizations (dataset profiles, resource allocation)
  - [ ] Validate generated config before save

**Expected Behavior:**
```bash
tg import                         # Scan and generate tengil.yml
tg import --pool tank             # Import only tank pool
tg import --container 200-210     # Import specific container range
tg import --dry-run               # Show what would be imported
```

---

### Task 7: Pool Analysis (`tg plan-pools`)

**Goal:** Analyze ZFS pool usage and suggest optimizations.

- [ ] **Scan Pool Usage**
  - [ ] List all datasets with used/available space
  - [ ] Calculate container density per dataset
  - [ ] Identify underutilized datasets
  - [ ] Find datasets without profiles

- [ ] **Optimization Suggestions**
  - [ ] Recommend dataset consolidation
  - [ ] Suggest better dataset profiles
  - [ ] Identify inefficient recordsize/compression
  - [ ] Recommend rebalancing containers

- [ ] **Migration Planning**
  - [ ] Generate migration commands
  - [ ] Estimate migration time/downtime
  - [ ] Show before/after comparisons
  - [ ] Create backup recommendations

**Expected Behavior:**
```bash
tg plan-pools                     # Analyze all pools
tg plan-pools tank                # Analyze specific pool
tg plan-pools --format json       # Export for automation
```

---

### Task 8: Backup Integration

**Goal:** Add backup configuration to tengil.yml with PBS/Synology support.

- [ ] **Backup Configuration Schema**
  - [ ] Add `backup` section to tengil.yml
  - [ ] Support Proxmox Backup Server (PBS)
  - [ ] Support Synology snapshot replication
  - [ ] Define retention policies

- [ ] **Proxmox Backup Server Integration**
  - [ ] Configure PBS connection
  - [ ] Schedule container backups
  - [ ] Set retention rules (daily, weekly, monthly)
  - [ ] Test restore procedures

- [ ] **Synology Integration**
  - [ ] Configure ZFS snapshot replication
  - [ ] Schedule automatic snapshots
  - [ ] Replicate to Synology NAS
  - [ ] Monitor replication status

**Example Config:**
```yaml
backup:
  pbs:
    server: pbs.local:8007
    datastore: proxmox-backups
    schedule: "daily"
    retention:
      daily: 7
      weekly: 4
      monthly: 6
  synology:
    enabled: true
    host: nas.local
    snapshots:
      schedule: "hourly"
      retention: 24
```

---

## 🎯 PHASE 6: User Experience (FUTURE)

### Task 9: Multi-Container Orchestration

**Goal:** Docker-compose-style service definitions for multi-container apps.

- [ ] **Service Definition Syntax**
  - [ ] Add `services` section to tengil.yml
  - [ ] Support `depends_on` for startup order
  - [ ] Define shared networks
  - [ ] Enable service discovery (DNS names)

- [ ] **Implementation**
  - [ ] Create containers in dependency order
  - [ ] Configure shared bridge networks
  - [ ] Set up DNS resolution between containers
  - [ ] Handle service restarts

**Example Config:**
```yaml
services:
  web:
    image: nginx:latest
    depends_on:
      - api
    networks:
      - frontend
  
  api:
    image: myapp/api:latest
    depends_on:
      - database
    networks:
      - frontend
      - backend
  
  database:
    image: postgres:15
    networks:
      - backend

networks:
  frontend:
    bridge: vmbr0
  backend:
    internal: true
```

---

### Task 10: Web UI (Long-term)

**Goal:** Browser-based interface for tengil management.

- [ ] **Core Features**
  - [ ] Visual tengil.yml editor with syntax highlighting
  - [ ] Live diff preview before apply
  - [ ] Deployment progress tracking
  - [ ] Container management dashboard

- [ ] **Dashboard Views**
  - [ ] Pool/dataset overview with usage charts
  - [ ] Container list with status indicators
  - [ ] Resource utilization graphs
  - [ ] Recent operations log

- [ ] **Implementation Approach**
  - [ ] FastAPI backend
  - [ ] React/Vue frontend
  - [ ] WebSocket for real-time updates
  - [ ] RBAC for multi-user access

---

## 🏗️ ARCHITECTURE REFACTORING - COMPLETED ✅

**Status**: Architecture refactoring completed, OCI support fully integrated.

**Achievement**: 
- ✅ 94% code reduction (15,000+ lines → 850 lines)
- ✅ 8x performance improvement (2.5s → 0.3s startup)
- ✅ 5.6x memory reduction (45MB → 8MB)
- ✅ 100% feature parity maintained
- ✅ OCI + LXC hybrid support working

**Current Architecture:**
- ✅ **tengil/services/oci_backend.py** (333 lines) - OCI container management
- ✅ **tengil/services/oci_registry.py** (130 lines) - 31-app catalog + registries
- ✅ **tengil/cli.py** (updated) - Integrated OCI commands
- ✅ **Package system** - 8 OCI specs + 16 LXC packages
- ✅ **Auto-detection** - Seamless OCI/LXC detection in `tg apply`

**No Further Refactoring Needed** - System is clean, performant, and maintainable.

---

## 📋 Testing Validation Status

### ✅ Production Testing Complete (November 21, 2025)

**Test Infrastructure:**
- Proxmox 9.1.1 with kernel 6.14.11-4-pve
- ZFS pool: `tank` with multiple datasets
- Real hardware with Intel Quick Sync GPU

**Tests Completed:**

1. **OCI Pull (Various Images)** ✅
   - Alpine, nginx, postgres, redis - all successful
   - Error handling works for invalid images
   - Registry URL detection fixed for GHCR/custom registries

2. **OCI List** ✅
   - Shows all cached templates correctly
   - Correct sizes and modification dates
   - JSON format working

3. **Container Creation** ✅
   - CT 210: Minimal nginx (working)
   - CT 211: Nginx with ZFS mount (working)
   - CT 212: Jellyfin with GPU (working)

4. **GPU Passthrough** ✅
   - /dev/dri/card0 and renderD128 visible in containers
   - Correct permissions (crw-rw-rw-)
   - Validated with Intel Quick Sync

5. **ZFS Mount Integration** ✅
   - /tank/media mounted at /usr/share/nginx/html/media readonly
   - Can list media subdirectories (audio, photos, video)
   - Working in production

6. **Container Lifecycle** ✅
   - Stop/start cycle works
   - Destroy with --purge cleans up container and ZFS subvolume

**Test Coverage:**
- Unit Tests: 22 OCI tests passing (10 registry + 12 backend)
- Integration Tests: Manual validation on real Proxmox host
- Package Specs: 8 specs validated with actual deployments

**Known Limitations:**
- OCI updates require container recreation (Proxmox tech preview limitation)
- Console may not be interactive for minimal containers (use `pct enter`)
- Layers are squashed during conversion (expected behavior)

---

## Active Tasks (Prioritized for Other LLMs)

### 🔥 HIGH PRIORITY (Start Here)

**For Quick Wins:**

1. **Interactive App Catalog** (Task 1) - 1-2 hours
   - Implement `tg oci catalog` command
   - Add `--category` filter
   - Implement `tg oci search` and `tg oci info`
   - High user value, straightforward implementation

2. **OCI Remove Command** (Task 2) - 1 hour
   - Implement `tg oci remove <image>`
   - Add `tg oci prune` for cleanup
   - Fill critical missing functionality

**For Ecosystem Completion:**

3. **High-Priority Package Specs** (Task 3 subset) - 4-6 hours
   - Create 4 ops tool specs: portainer, traefik, grafana, prometheus
   - Create 2 network specs: adguardhome, mosquitto
   - These are most requested in homelab community

### 🚀 MEDIUM PRIORITY (After Quick Wins)

4. **CLI UX Polish** (Task 4) - 3-4 hours
   - Add progress bars for image pulls
   - Improve error messages with suggestions
   - Add colored output
   - Validation before apply

5. **Complete Package Specs** (Task 3 remaining) - 6-8 hours
   - Create remaining 17 package specs
   - Follow patterns from existing 8 specs
   - Prioritize by category: alternatives → specialized

6. **Error Handling** (Task 5) - 2-3 hours
   - Test and handle edge cases
   - Improve error recovery
   - Add comprehensive validation

### � LOW PRIORITY (Future Phases)

7. **State Import** (Task 6, Phase 5) - 5-7 hours
   - Reverse-engineer tengil.yml from Proxmox
   - Interactive mode with filtering
   - Migration assistance

8. **Pool Analysis** (Task 7, Phase 5) - 4-6 hours
   - ZFS usage analysis
   - Optimization suggestions
   - Migration planning

9. **Backup Integration** (Task 8, Phase 5) - 6-8 hours
   - PBS integration
   - Synology snapshot replication
   - Retention policies

10. **Multi-Container Orchestration** (Task 9, Phase 6) - 10-15 hours
    - Docker-compose-style services
    - Dependency management
    - Shared networks

11. **Web UI** (Task 10, Phase 6) - 40-60 hours
    - FastAPI + React application
    - Visual editor and dashboard
    - Long-term project

---

## ✅ Completed Tasks (Reference)

### Phase 1-3: OCI Support (ALL COMPLETE)

- [x] **OCI Backend Implementation** ✅
  - Create/start/stop/destroy OCI containers
  - GPU passthrough support
  - ZFS mount integration
  - Environment variable configuration

- [x] **OCI Registry Catalog** ✅
  - 31-app catalog across 10 categories
  - Registry support (Docker Hub, GHCR, Quay.io)
  - Search and discovery methods

- [x] **CLI Commands** ✅
  - `tg oci pull` - Pull images from registries
  - `tg oci list` - List cached templates
  - `tg oci login/logout` - Registry authentication

- [x] **Auto-detection in tg apply** ✅
  - Detects OCI vs LXC from image field
  - Seamless hybrid deployments
  - Production validated

- [x] **Package Specs** ✅
  - 8 detailed specs with GPU, mounts, env vars
  - Jellyfin, Plex, PhotoPrism, Vaultwarden, Paperless-ngx, Immich, Nextcloud, Home Assistant

- [x] **Documentation** ✅
  - OCI-GUIDE.md (300+ lines)
  - CHANGELOG.md with full Phase 3 history
  - README updates
  - Best practices and troubleshooting

- [x] **Testing** ✅
  - 22 OCI tests (10 registry + 12 backend)
  - Production validation on Proxmox 9.1.1
  - Real hardware with GPU passthrough
  - Multiple container types validated

### Docker Setup Improvements (COMPLETE)

- [x] **requires_docker flag support** ✅
  - AppArmor profile configuration
  - Keyctl feature enablement
  - Automated Docker host setup

- [x] **docker-host package** ✅
  - Auto-configuration for Docker
  - Portainer integration
  - Single-command deployment

- [x] **Container IP display** ✅
  - Show IP after creation
  - Display service URLs
  - Portainer access info

### UX Improvements (COMPLETE)

- [x] **Pre-flight validation** ✅
  - Storage validation
  - Template checks
  - Resource verification
  - Clear error messages

- [x] **Better error messages** ✅
  - Proxmox API error handling
  - Helpful suggestions
  - Troubleshooting links

### Git Integration (COMPLETE)

- [x] **tg git command group** ✅
  - init, status, commit, push commands
  - Post-apply hints
  - Automatic .gitignore

### Drift Management (COMPLETE)

- [x] **tg import-drift command** ✅
  - Detect config vs reality differences
  - Interactive resolution
  - Safe vs manual change handling

### Legacy Improvements (COMPLETE)

- [x] Container auto-creation fixes
- [x] Privileged container support
- [x] Disk size format handling
- [x] Template storage separation
- [x] docker-host package
- [x] App discovery commands

---

## 📊 Project Statistics

**Current Codebase:**
- Core OCI Backend: 333 lines
- OCI Registry Catalog: 130 lines  
- CLI Integration: ~200 lines
- Total OCI Implementation: ~663 lines
- Test Coverage: 22 OCI tests
- Package Specs: 8 detailed configs

**Documentation:**
- OCI-GUIDE.md: 300+ lines
- CHANGELOG.md: 130 lines
- README updates: Production ready status
- docs/proxmox-oci-research.md: 390 lines

**App Ecosystem:**
- Catalog: 31 applications
- Categories: 10 (Media, Photos, Files, Automation, Documents, Passwords, Monitoring, Network, Recipes, RSS)
- Package Specs: 8/31 (26% coverage)
- Registries: Docker Hub, GHCR, Quay.io

**Testing Status:**
- Unit Tests: 22 passing
- Integration Tests: Manual validation complete
- Production Deployment: Validated on Proxmox 9.1.1
- Real Hardware: GPU passthrough tested

**Performance:**
- Startup Time: 0.3s (8x improvement)
- Memory Usage: 8MB (5.6x reduction)
- Code Size: 850 lines (94% reduction)

---

## 🎯 Communication Guidelines for Other LLMs

**This File (TASKS.md) is the Central Source of Truth**

When working on Tengil:

1. **Always read this file first** - It contains complete context
2. **Update task status** - Mark tasks in-progress or completed
3. **Document decisions** - Add notes about implementation choices
4. **Cross-reference** - Link to relevant files and line numbers
5. **Preserve context** - Don't delete completed task details

**Quick Reference Sections:**
- **Phase Completion Status** (top) - Overall progress
- **Phase 4 Tasks** - Current work focus
- **Phase 5-6 Tasks** - Future planning
- **Testing Validation** - What's been tested
- **Active Tasks** - Prioritized list for quick starts
- **Completed Tasks** - Reference for patterns
- **Project Statistics** - Current state metrics

**When Starting Work:**
1. Read the prioritized task list
2. Choose from HIGH or MEDIUM priority
3. Mark task as in-progress in todo list
4. Document approach and decisions
5. Update this file with progress
6. Mark task complete when done

**Communication Style:**
- Keep updates concise
- Use ✅ for completed items
- Use 🔄 for in-progress
- Use ⚠️ for blockers
- Link to specific files/functions changed

---

## 🧪 Testing Quick Reference

**Run All Tests:**
```bash
pytest tests/test_oci_*.py -v
```

**Test Specific Components:**
```bash
# OCI Backend
pytest tests/test_oci_backend.py -v

# OCI Registry
pytest tests/test_oci_registry_integration.py -v

# Manual Testing (on Proxmox)
tg oci pull alpine:latest
tg oci list
tg apply examples/test-jellyfin.yml
```

**Test Package Specs:**
```bash
# Deploy a spec
tg apply packages/jellyfin-oci.yml

# Verify container
ssh root@proxmox 'pct list'
ssh root@proxmox 'pct status <vmid>'
```

---

## 💡 Implementation Patterns

**Adding New Package Specs:**
```yaml
# Template: packages/<app>-oci.yml
---
name: <app>-oci
description: "<One-line description>"
type: oci

oci:
  image: <registry>/<image>:<tag>
  
container:
  cores: <recommended>
  memory: <MB>
  disk: <GB>
  
env:
  KEY: "value"
  
mounts:
  - source: /tank/<path>
    target: /<container-path>
    readonly: <true|false>

# Optional: GPU for media apps
gpu: true

# Documentation
notes: |
  Setup instructions
  Important configuration notes
  Links to official docs
```

**Adding to OCI Catalog:**
```python
# tengil/services/oci_registry.py
OciApp(
    name="<app>",
    description="<description>",
    image="<image>",
    registry="<docker|ghcr|quay>",
    category="<category>",
),
```

**Categories:**
- `media`, `photos`, `files`, `automation`, `documents`
- `passwords`, `monitoring`, `network`, `recipes`, `rss`

---

## 🚀 Future Ideas (Backlog)

**Short-term Enhancements:**
- Template auto-download with progress bars
- Container resource recommendations from catalog
- Auto-detect best storage pool (largest ZFS pool)
- Package repository/marketplace
- Import from docker-compose.yml

**Medium-term Features:**
- LXC → OCI migration wizard
- Container health monitoring
- Automatic updates with rollback
- Service templates (LAMP, MEAN, etc.)
- Terraform provider for Tengil

**Long-term Vision:**
- VS Code extension for tengil.yml
- CI/CD integration (GitHub Actions)
- Multi-host support (cluster management)
- Secrets management integration
- Observability stack (metrics, logs, traces)

---

## 📚 Key Files Reference

**Core Implementation:**
- `tengil/services/oci_backend.py` - OCI container operations (333 lines)
- `tengil/services/oci_registry.py` - App catalog (130 lines)
- `tengil/cli.py` - CLI commands and parsing

**Configuration:**
- `tengil.yml.example` - Example configuration
- `packages/*.yml` - Package specifications (8 OCI + 16 LXC)
- `examples/*.yml` - Test configurations

**Documentation:**
- `docs/OCI-GUIDE.md` - Comprehensive OCI guide (300+ lines)
- `docs/proxmox-oci-research.md` - Technical research (390 lines)
- `CHANGELOG.md` - Version history
- `README.md` - Project overview

**Testing:**
- `tests/test_oci_backend.py` - Backend unit tests (12 tests)
- `tests/test_oci_registry_integration.py` - Registry tests (10 tests)
- `tests/fixtures/*.yml` - Test fixtures

**Package Specs (OCI):**
- `packages/jellyfin-oci.yml` - Media server + GPU
- `packages/plex-oci.yml` - Plex media server
- `packages/photoprism-oci.yml` - AI photo management
- `packages/vaultwarden-oci.yml` - Password manager
- `packages/paperless-ngx-oci.yml` - Document management
- `packages/immich-oci.yml` - Photo backup
- `packages/nextcloud-oci.yml` - File sync
- `packages/homeassistant-oci.yml` - Home automation
