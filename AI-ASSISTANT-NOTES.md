# 🤖 Notes for AI Assistants

**Project:** Tengil - Declarative Proxmox infrastructure tool  
**Current Phase:** OCI container support implementation  
**Date:** November 21, 2025

---

## 🚨 Critical Design Decisions

### 1. OCI Implementation: CLI-Based, NOT Web UI APIs

**DECISION:** We use direct CLI commands (skopeo + pct), NOT Proxmox Web UI APIs.

#### Why CLI?
- ✅ **More reliable** - No HTTP/authentication overhead
- ✅ **Faster** - Direct subprocess execution
- ✅ **Simpler** - No requests/urllib dependencies
- ✅ **Standard** - Proxmox Web UI calls same commands internally
- ✅ **Proven** - All commands tested on production (192.168.1.42)

#### Implementation Example
```python
# ✅ What we do (direct CLI)
import subprocess
subprocess.run(['skopeo', 'copy', 'docker://...', 'oci-archive:/path'])
subprocess.run(['pct', 'create', '200', 'local:vztmpl/image.tar'])

# ❌ What we DON'T do (HTTP API)
import requests
requests.post('https://proxmox:8006/api2/json/...', ...)
```

#### Don't Suggest
- ❌ Researching "Pull from OCI Registry" Web UI menu
- ❌ Capturing browser DevTools network traffic
- ❌ Using pvesh/pvecm for OCI operations
- ❌ Adding HTTP client dependencies (requests, urllib)

#### DO Suggest
- ✅ Improving CLI command generation
- ✅ Better error handling for subprocess calls
- ✅ Adding more OCI package specs
- ✅ Registry authentication via CLI flags

---

## 📁 Project Structure

```
tengil/
├── tengil/services/proxmox/backends/  # Backend abstraction layer
│   ├── base.py         # Abstract ContainerBackend interface
│   ├── lxc.py          # Traditional LXC backend
│   ├── oci.py          # OCI backend (skopeo + pct)
│   └── README.md       # Architecture documentation
├── packages/           # Pre-built OCI package specs
│   ├── jellyfin-oci.yml
│   ├── homeassistant-oci.yml
│   ├── nextcloud-oci.yml
│   └── immich-oci.yml
├── tests/
│   └── test_oci_backend.py  # 12 tests, all passing ✅
└── docs/
    └── proxmox-oci-research.md  # Comprehensive research findings
```

---

## ✅ What's Completed

### Phase 1: Research (DONE)
- ✅ OCI workflow validated (skopeo → pct)
- ✅ Manual deployments tested (Alpine, Jellyfin)
- ✅ GPU passthrough confirmed working
- ✅ Documentation written

### Phase 2: Implementation (DONE)
- ✅ Backend abstraction layer created
- ✅ OCIBackend class implemented (295 lines)
- ✅ LXCBackend class implemented (158 lines)
- ✅ Unit tests written (12/12 passing)
- ✅ OCI package specs created (4 apps)

### Current: Phase 3 (IN PROGRESS)
- 🟡 CLI integration (tg oci pull/list/search)
- ⏳ Auto-detection (OCI vs LXC in tg apply)

---

## 🎯 Production Validation

**Server:** 192.168.1.42 (Proxmox 9.1.1, Kernel 6.14.11-4-pve)

**Working Deployments:**
- **Alpine (CT 199):** 3.7MB, system container ✅
- **Jellyfin (CT 202):** 500MB, app container ✅
  - GPU: /dev/dri/card0, renderD128 (Intel AlderLake-S GT1)
  - Media: /tank/media mounted at /media (readonly)
  - Volumes: /config, /cache (auto-created)
  - Web UI: http://192.168.1.42:8096

**Performance:**
- Traditional LXC: 10-15 minutes (download + scripts + config)
- OCI Backend: ~2 minutes (pull + create)
- **Improvement: 5-7x faster** ⚡

---

## 🔧 Key Implementation Details

### OCIBackend Workflow

```python
# 1. Pull image with skopeo
backend.pull_image('jellyfin/jellyfin', 'latest')
# → Stores: /var/lib/vz/template/cache/jellyfin-latest.tar

# 2. Create container
backend.create_container(spec, storage='tank')
# → Runs: pct create 200 local:vztmpl/jellyfin-latest.tar ...
# → Output: "Detected OCI archive"

# 3. Configure GPU (if specified)
backend.configure_gpu(vmid=200)
# → Runs: pct set 200 --dev0 /dev/dri/card0,mode=0666 ...

# 4. Add mounts (if specified)
backend._add_mount(vmid=200, mount={...})
# → Runs: pct set 200 --mp0 /tank/media,mp=/media,ro=1
```

### Command Verification

All generated commands verified against:
- ✅ `man pct` (Proxmox VE documentation)
- ✅ `man skopeo` (Skopeo documentation)
- ✅ Manual testing on production server
- ✅ See `.local/PROXMOX-CLI-VERIFICATION.md` for details

---

## 📚 Documentation Hierarchy

**For AI Assistants (you!):**
1. **THIS FILE** - Quick design decisions
2. `tengil/services/proxmox/backends/README.md` - Architecture details
3. `.local/OCI-BACKEND-SUMMARY.md` - Full implementation summary

**For Users:**
1. `README.md` - Project overview
2. `docs/USER_GUIDE.md` - Complete guide
3. `docs/proxmox-oci-research.md` - OCI implementation research

**For Developers:**
1. `tests/test_oci_backend.py` - Test examples
2. `.local/PROXMOX-CLI-VERIFICATION.md` - Command validation
3. Package specs in `packages/` - Real-world examples

---

## 🎨 Code Style

### Backend Pattern (Strategy Pattern)

```python
# Automatic backend selection
def select_backend(spec: Dict) -> ContainerBackend:
    if 'oci' in spec:
        return OCIBackend()
    elif 'template' in spec:
        return LXCBackend()
    else:
        raise ValueError("Unknown container type")

# Usage
backend = select_backend(spec)
vmid = backend.create_container(spec, storage='tank')
backend.start_container(vmid)
```

### Testing Pattern (Mock subprocess)

```python
from unittest.mock import patch

def test_pull_image():
    backend = OCIBackend(mock=True)  # Mock mode for development
    result = backend.pull_image('alpine', 'latest')
    assert result == 'local:vztmpl/alpine-latest.tar'

@patch('subprocess.run')
def test_real_commands(mock_run):
    backend = OCIBackend(mock=False)
    mock_run.return_value = MagicMock(returncode=0)
    backend.pull_image('alpine', 'latest')
    # Verify subprocess.run was called with correct args
    assert mock_run.call_args[0][0] == ['skopeo', 'copy', ...]
```

---

## 🐛 Common Pitfalls

### 1. Don't Mix CLI and API Approaches
```python
# ❌ WRONG: Mixing subprocess and HTTP
subprocess.run(['pct', 'create', ...])
requests.post(f'{api}/nodes/{node}/lxc', ...)  # Unnecessary!

# ✅ RIGHT: Use CLI consistently
subprocess.run(['pct', 'create', ...])
subprocess.run(['pct', 'set', ...])
subprocess.run(['pct', 'start', ...])
```

### 2. Don't Hardcode Paths
```python
# ❌ WRONG
template_path = '/var/lib/vz/template/cache/image.tar'

# ✅ RIGHT
from pathlib import Path
template_dir = Path('/var/lib/vz/template/cache')
template_path = template_dir / f'{image_name}-{tag}.tar'
```

### 3. Always Handle Subprocess Errors
```python
# ❌ WRONG
subprocess.run(cmd)  # Ignores errors!

# ✅ RIGHT
try:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True  # Raises CalledProcessError on failure
    )
except subprocess.CalledProcessError as e:
    print(f"Error: {e.stderr}")
    return None
```

---

## 🔮 Roadmap

### Next (Phase 3)
- [ ] CLI commands: `tg oci pull`, `tg oci list`, `tg oci search`
- [ ] Auto-detect backend in `tg apply` based on spec format
- [ ] Registry authentication support

### Future (Phase 4+)
- [ ] Expand catalog to 30+ curated apps
- [ ] Multi-container orchestration (Immich-style)
- [ ] Private registry support
- [ ] Multi-arch images (arm64)
- [ ] LXC→OCI migration tooling

---

## 💡 Contribution Guidelines

When suggesting code changes:

1. **Maintain CLI-first approach** - Don't introduce API dependencies
2. **Follow backend pattern** - Both LXC and OCI implement same interface
3. **Add tests** - Mock subprocess calls, verify commands
4. **Document commands** - Reference Proxmox man pages
5. **Preserve backward compatibility** - LXCBackend for existing users

---

## 🤝 Questions?

- **Implementation details:** See `.local/OCI-BACKEND-SUMMARY.md`
- **Command verification:** See `.local/PROXMOX-CLI-VERIFICATION.md`
- **Research findings:** See `docs/proxmox-oci-research.md`
- **Architecture:** See `tengil/services/proxmox/backends/README.md`

**Key Principle:** When in doubt, use CLI commands. The Proxmox Web UI is just a wrapper around the same tools we're using directly.
