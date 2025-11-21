# Proxmox Container Backends

**Architecture:** Backend abstraction layer for LXC and OCI containers

---

## 🏗️ Design Pattern

This directory implements the **Strategy Pattern** for container management:

```
ContainerBackend (Abstract)
├── LXCBackend (Traditional LXC templates)
└── OCIBackend (OCI images via skopeo)
```

Both backends implement the same interface, allowing seamless switching between LXC and OCI containers.

---

## 📁 Files

### `base.py` (95 lines)
Abstract `ContainerBackend` interface defining the contract:

```python
class ContainerBackend(ABC):
    create_container(spec, storage, pool) -> Optional[int]
    start_container(vmid) -> bool
    stop_container(vmid, timeout) -> bool
    destroy_container(vmid, purge) -> bool
    container_exists(vmid) -> bool
    configure_gpu(vmid, gpu_type) -> bool
```

### `lxc.py` (158 lines)
Traditional LXC backend using Proxmox LXC templates:

```python
backend = LXCBackend()
vmid = backend.create_container({
    'template': 'local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst',
    'hostname': 'mycontainer',
    'cores': 2,
    'memory': 2048
})
```

**Use for:** Traditional LXC deployments, backward compatibility

### `oci.py` (295 lines)
OCI backend using skopeo + Proxmox OCI support:

```python
backend = OCIBackend()
vmid = backend.create_container({
    'oci': {
        'image': 'jellyfin/jellyfin',
        'tag': 'latest',
        'registry': 'docker.io'
    },
    'hostname': 'jellyfin',
    'cores': 4,
    'memory': 4096,
    'gpu': {'passthrough': True}
})
```

**Use for:** New deployments, OCI images from Docker Hub/GHCR

---

## 🚨 IMPORTANT: Implementation Approach

### We Use CLI Commands, Not APIs

Both backends use **direct subprocess calls** to Proxmox CLI tools:

```python
# OCIBackend approach
subprocess.run(['skopeo', 'copy', 'docker://...', 'oci-archive:/path'])
subprocess.run(['pct', 'create', '200', 'local:vztmpl/...'])
subprocess.run(['pct', 'set', '200', '--dev0', '/dev/dri/card0'])
```

**Why CLI instead of Web UI/API?**
1. ✅ **More reliable** - No network/auth overhead
2. ✅ **Faster** - Direct execution
3. ✅ **Simpler** - No HTTP dependencies
4. ✅ **Standard** - Proxmox Web UI calls same commands
5. ✅ **Proven** - Tested on production (192.168.1.42)

**Don't suggest researching:**
- ❌ Proxmox Web UI "Pull from OCI Registry" menu
- ❌ Browser DevTools API capture
- ❌ pvesh JSON endpoints for OCI
- ❌ Adding requests/urllib dependencies

---

## ✅ Validation Status

### Testing
- **Unit Tests:** 12/12 passing (`tests/test_oci_backend.py`)
- **Integration:** Mock mode for development
- **Production:** Tested on Proxmox 9.1.1 (192.168.1.42)

### Working Deployments
- **Alpine (CT 199):** 3.7MB, system container ✅
- **Jellyfin (CT 202):** 500MB, GPU transcoding ✅
  - GPU passthrough: `/dev/dri/card0`, `renderD128`
  - ZFS mount: `/tank/media` → `/media`
  - Auto-volumes: `/config`, `/cache`

### Command Verification
All generated commands verified against:
- ✅ `man pct` (Proxmox documentation)
- ✅ `man skopeo` (Skopeo documentation)
- ✅ Manual testing on production server
- ✅ See `.local/PROXMOX-CLI-VERIFICATION.md`

---

## 🔧 Usage Examples

### Selecting Backend

```python
# Automatically select based on spec
if 'oci' in spec:
    backend = OCIBackend()
elif 'template' in spec:
    backend = LXCBackend()
else:
    raise ValueError("Unknown container type")

vmid = backend.create_container(spec)
```

### OCI Container (Jellyfin)

```python
from tengil.services.proxmox.backends import OCIBackend

backend = OCIBackend(mock=False)

spec = {
    'oci': {
        'image': 'jellyfin/jellyfin',
        'tag': 'latest'
    },
    'hostname': 'jellyfin',
    'cores': 4,
    'memory': 4096,
    'disk': 16,
    'gpu': {'passthrough': True},
    'features': {'nesting': True},
    'mounts': [
        {'source': '/tank/media', 'target': '/media', 'readonly': True}
    ]
}

# Pull image (if not cached)
template = backend.pull_image('jellyfin/jellyfin', 'latest')

# Create container
vmid = backend.create_container(spec, storage='tank')

# Start
backend.start_container(vmid)
```

### LXC Container (Debian)

```python
from tengil.services.proxmox.backends import LXCBackend

backend = LXCBackend(mock=False)

spec = {
    'template': 'local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst',
    'hostname': 'debian-server',
    'cores': 2,
    'memory': 2048,
    'disk': 8
}

vmid = backend.create_container(spec, storage='local-lvm')
backend.start_container(vmid)
```

---

## 📊 Performance

**OCI vs Traditional LXC Deployment:**

| Stage | Traditional LXC | OCI Backend | Improvement |
|-------|-----------------|-------------|-------------|
| Template Download | 2-3 min | 30-60 sec (cached after first) | 2-4x faster |
| Post-install Script | 5-10 min | 0 sec (not needed) | ∞ |
| Manual Config | 2-5 min | 10 sec (automated) | 12-30x faster |
| **Total** | **10-15 min** | **~2 min** | **5-7x faster** |

---

## 🔮 Future Enhancements

### OCIBackend TODO
- [ ] Registry authentication (Docker Hub tokens)
- [ ] Private registry support
- [ ] Multi-arch image support (arm64)
- [ ] Image layer caching optimization
- [ ] Dynamic `_get_next_mp_slot()` (currently hardcoded to mp0)

### LXCBackend TODO
- [ ] Refactor from existing `lifecycle.py`
- [ ] Template download progress tracking
- [ ] Template caching logic

---

## 📚 Documentation

- **Research:** `docs/proxmox-oci-research.md` (comprehensive findings)
- **CLI Verification:** `.local/PROXMOX-CLI-VERIFICATION.md` (command testing)
- **Implementation:** `.local/OCI-BACKEND-SUMMARY.md` (full summary)
- **Tests:** `tests/test_oci_backend.py` (12 test cases)

---

## 🤝 Contributing

When adding features to backends:

1. **Maintain interface compatibility** - Both backends must implement all abstract methods
2. **Use CLI commands** - Don't introduce HTTP API dependencies
3. **Add tests** - Mock subprocess calls for unit tests
4. **Document commands** - Verify against Proxmox man pages
5. **Test on production** - Validate on real Proxmox server (192.168.1.42)

---

**Questions?** See `.local/OCI-BACKEND-SUMMARY.md` for full implementation details.
