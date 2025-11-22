# Bugs Found During Full Deployment Testing
## Session: 22 November 2025

### Bug #1: State file not invalidated when config changes
**Severity:** High  
**Status:** ✅ Fixed  
**Fix:** StateStore now fingerprints `tengil.yml` and auto-invalidates cached state when the config changes. Default config path follows the state location to avoid cwd issues.

### Bug #2: MOCK mode appearing in diff output
**Severity:** Medium
**Status:** ✅ Fixed
**Found:** Running `tg diff` shows "MOCK: Would list datasets"
**Symptom:** Logs show MOCK operations even on real server
**Root Cause:** ZFSManager, ProxmoxManager, and NASManager checked `TG_MOCK` environment variable directly without safety valve logic
**Fix:** Updated all three manager classes to use the same safety valve as `is_mock()` helper - automatically disables mock mode on real Proxmox (when /etc/pve exists) unless `TG_MOCK_FORCE=1` is set

### Bug #3: Container creation fails - "filesystem successfully created, but not mounted"
**Severity:** Critical  
**Found:** Running `tg apply` with auto_create containers  
**Symptom:** `pct create` returns exit 255: "zfs error: filesystem successfully created, but not mounted"  
**Affected:** immich (201), jellyfin (200)  
**Details:**
```
ERROR    Failed to create container 201: Command '['pct', 'create', '201', ...
ERROR    Error output: unable to create CT 201 - zfs error: filesystem successfully created, but not mounted
```
**RESOLVED - False Positive:** 
- Containers DID get created successfully and are running
- The error message "filesystem successfully created, but not mounted" is misleading
- Both immich (201) and jellyfin (200) were created and started
- **Root Cause**: pct returns exit 255 but actually succeeds
- **Fix:** LXC backend now re-checks with `pct status` and treats the container as created when Proxmox returns a false-negative error.

### Bug #4: Wrong container selected for syncthing mount
**Severity:** High  
**Found:** After immich/jellyfin creation failures  
**Symptom:** Mount added to wrong container - "jellyfin-oci" (202) instead of "syncthing" (202)  
**Details:**
```
INFO     Adding mount point to container 202: mp1=/tank/syncthing,mp=/var/lib/syncthing,ro=1
INFO     ✓ Mounted /tank/syncthing → jellyfin-oci:/var/lib/syncthing
```
**Root Cause:** VMID 202 is jellyfin-oci (old test container), not syncthing  
**Impact:** Mounts go to wrong containers when VMIDs don't match names  
**Fix:** Mount orchestration now aborts if the vmid's hostname doesn't match the requested container name, preventing accidental mounts to the wrong CT.

---
*More bugs will be added as testing continues*

### Bug #5: Config file search path incorrect
**Severity:** Critical  
**Status:** ✅ Fixed (search order) / 🔍 Pending (debug warning)  
**Found:** Running `tg diff` without `--config` flag  
**Symptom:** Loads wrong/old config despite `/root/tengil.yml` being present and recent  
**Workaround (old):** Must use `tg diff --config /root/tengil.yml`  
**Root Cause:** Config file discovery didn't prioritize CWD `tengil.yml`  
**Fix:** Config search order is now `./tengil.yml` → `~/tengil-configs/tengil.yml` → `/etc/tengil/tengil.yml`.  
**Status update:** CLI now logs the chosen config and warns if multiple candidates exist.

### Bug #6: Env vars not applied to existing containers
**Severity:** High  
**Status:** ✅ Fixed  
**Found:** Updating `env:` in config didn’t push changes to running containers  
**Fix:** Apply workflow now issues `pct set --env` for both OCI and LXC containers and restarts running containers to pick up changes. CLI added `tg container env` for manual updates.

### Bug #6: scan command doesn't load desired config
**Severity:** Critical  
**Status:** ✅ Fixed  
**Fix:** `tg scan` now accepts `--config` and records a desired snapshot (from that config) alongside reality in the state store. Fingerprints the config path to keep desired/reality aligned for follow-up diff/apply runs.

### Bug #7: Config format confusion - `backend:` vs `type:` for OCI containers
**Severity:** Medium (Documentation)  
**Status:** ✅ Fixed (parser + validation)  
**Fix:** Parser now normalizes OCI specs and accepts either `type: oci` with `oci.image` or top-level `image: nginx:alpine`. Validation errors point to the correct fields; docs updated to prefer `type: oci` + `oci.image/tag`.

### Bug #8: Config schema mismatch - OCI containers need top-level `image` field
**Severity:** High (Config Format)  
**Status:** ✅ Fixed (schema)  
**Fix:** OCI containers now accept both forms: top-level `image: nginx:alpine` or nested `oci.image/tag`. Parser normalizes and validator enforces presence of an OCI image when `type: oci` and `auto_create=true`.

---

## Bug #9: YAML Boolean Conversion for ZFS Properties

**Status:** ✅ FIXED in commit d59ccbe

**Tested:** Successfully created tank/media-test with `atime: off` and `compression: off`

### Problem Description

YAML 1.1 spec treats `off`, `on`, `yes`, `no`, `true`, `false` as boolean keywords. When these appear unquoted in YAML, they are converted to Python `True`/`False` boolean values. ZFS command-line tools require exact string values like `"off"` and `"on"`, not boolean conversions.

### Reproduction

```yaml
zfs:
  atime: off         # Parsed as False
  compression: off   # Parsed as False
  atime: on          # Parsed as True
  compression: on    # Parsed as True
```

When Tengil creates the dataset:
```bash
zfs create -o atime=False -o compression=False tank/test
# Error: 'atime' must be one of 'on | off'
# Error: 'compression' must be one of 'on | off | lzjb | ...'
```

### Root Cause

1. YAML parser (`ruamel.yaml` or `PyYAML`) converts reserved keywords to booleans
2. Config loader passes boolean values through without conversion
3. ZFS manager uses f-string interpolation: `f"{key}={value}"` → `"atime=False"`
4. ZFS rejects `False`/`True` as invalid property values

### Attempted Workarounds

**Quoting doesn't work:**
```yaml
zfs:
  atime: "off"   # YAML parser STILL converts to False!
```

**Using alternate values:**
```yaml
zfs:
  atime: on      # Becomes True, ZFS also rejects this!
  compression: lz4  # Works - not a YAML keyword
```

### Fix

ZFS manager now normalizes boolean properties to `on`/`off` for `create`, `set`, and property sync. YAML boolean coercion no longer breaks atime/compression settings.

---

## Bug #10: LXC Template Filename Resolution

**Status:** ✅ FIXED in commit 2b460d2

**Severity:** High - Blocked LXC container creation

**Impact:** LXC containers couldn't be created with short template names

### Problem Description

Proxmox stores templates with full version suffixes:
```
/var/lib/vz/template/cache/debian-12-standard_12.12-1_amd64.tar.zst
```

But users want to reference them with short names in config:
```yaml
template: debian-12-standard
```

Old code simply appended `.tar.zst`:
```python
template_file = template if '.tar' in template else f'{template}.tar.zst'
# Resulted in: debian-12-standard.tar.zst (WRONG)
```

This caused `pct create` to fail:
```
unable to create CT 502 - volume 'local:vztmpl/debian-12-standard.tar.zst' does not exist
```

### Solution Implemented

Added `resolve_template_filename()` method to `TemplateManager` class:

```python
def resolve_template_filename(self, template: str) -> str:
    """Resolve short template name to full filename with version."""
    result = self.node.ssh_run("pveam list local", check=True)
    for line in result.stdout.splitlines():
        if template in line and '.tar' in line:
            # Extract: local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst
            parts = line.split()
            if parts and ':vztmpl/' in parts[0]:
                return parts[0].split(':vztmpl/')[1]
    return f'{template}.tar.zst'  # Fallback
```

Updated `lifecycle.py` to use resolver:
```python
template_file = self.templates.resolve_template_filename(template)
```

**Result:** LXC containers now create successfully with short template names like `debian-12-standard`.

---

## Bug #11: Additional Mounts Not Applied to Containers

**Status:** ✅ FIXED (commit 6a86aad)

**Severity:** Medium (Was blocking additional mount functionality)

**Impact:** Additional mounts from `mounts:` field in container spec were not being applied

### Problem Description

When a container spec included a `mounts:` section with additional mount points, only the primary dataset mount was applied. Additional mounts were parsed but never actually mounted to the container.

### Reproduction (Before Fix)

```yaml
containers:
  - name: jellyfin-test
    vmid: 502
    mount: /config  # Primary mount - WORKS ✅
    mounts:         # Additional mounts - NOT APPLIED ❌
      - source: /tank/media-test
        target: /media
        readonly: true
```

**Expected behavior:**
- Container should have two mount points: `mp0` (primary) and `mp1` (additional)

**Actual behavior (before fix):**
```bash
pct config 502 | grep mp
# mp0: /tank/jellyfin-test,mp=/config,ro=1
# (missing mp1)
```

### Root Cause

Additional mounts needed to be applied AFTER container creation and primary mount setup, but there was no code path that:
1. Extracted `mounts:` from container spec
2. Called `add_container_mount()` for each additional mount
3. Applied them post-creation

### Fix Implementation

**Location:** [orchestrator.py:462-524](tengil/services/proxmox/containers/orchestrator.py#L462-L524)

Added `_apply_additional_mounts()` method that:
1. Extracts `mounts:` array from container spec
2. Validates source/target for each mount
3. Checks if mount already exists (idempotent operation)
4. Finds next available mount point (mp1, mp2, etc.)
5. Applies via `add_container_mount()` with proper readonly flag
6. Logs success/failure for each mount

**Caller:** `setup_container_mounts()` at [orchestrator.py:428-429](tengil/services/proxmox/containers/orchestrator.py#L428-L429)
- Called AFTER primary mount succeeds
- Only triggered if container spec is a dict and has `mounts:` field

### Code Changes

```python
def _apply_additional_mounts(self, vmid: int, container_spec: Dict, container_name: Optional[str] = None) -> bool:
    """Apply additional mounts from container spec's mounts: field."""
    additional_mounts = container_spec.get('mounts', [])
    if not additional_mounts:
        return True

    logger.info(f"Applying {len(additional_mounts)} additional mount(s) to container {vmid}")

    success_count = 0
    for mount in additional_mounts:
        source = mount.get('source')
        target = mount.get('target')
        readonly = mount.get('readonly', False)

        # Check if already exists (idempotent)
        if self.mounts.container_has_mount(vmid, source):
            logger.info(f"  ✓ Additional mount already exists: {source} → {target}")
            success_count += 1
            continue

        # Find next free mount point
        mp_num = self.mounts.get_next_free_mountpoint(vmid)

        # Add the mount
        if self.mounts.add_container_mount(vmid, mp_num, source, target, readonly, container_name):
            logger.info(f"  ✓ Added additional mount: {source} → {target} (readonly={readonly})")
            success_count += 1
        else:
            logger.error(f"  ✗ Failed to add mount: {source} → {target}")

    return success_count == len(additional_mounts)
```

### Testing & Verification

**Test Case:** Container 502 (jellyfin-test)
```yaml
containers:
  - name: jellyfin-test
    vmid: 502
    mount: /config
    mounts:
      - source: /tank/media-test
        target: /media
        readonly: true
```

**Deploy Logs:**
```
INFO     Applying 1 additional mount(s) to container 502
INFO     Permission manager determined readonly=True for jellyfin-test -> /tank/media-test
INFO     Adding mount point to container 502: mp1=/tank/media-test,mp=/media,ro=1
INFO       ✓ Added additional mount: /tank/media-test → /media (readonly=True)
INFO     Applied 1/1 additional mount(s)
```

**Verification Commands:**
```bash
# Check mount points exist
pct config 502 | grep mp
mp0: /tank/jellyfin-test,mp=/config,ro=1
mp1: /tank/media-test,mp=/media,ro=1        # ✅ ADDITIONAL MOUNT PRESENT

# Check mount is accessible inside container
pct exec 502 -- ls -la /media
total 9
drwxr-xr-x  2 nobody nogroup  2 Nov 22 00:54 .  # ✅ MOUNTED AND ACCESSIBLE
drwxr-xr-x 18 root   root    22 Nov 22 01:10 ..
```

**Result:**
- ✅ `mp0` created for `/tank/jellyfin-test` → `/config` (primary mount)
- ✅ `mp1` created for `/tank/media-test` → `/media` (additional mount, readonly)
- ✅ Both mounts accessible inside container
- ✅ Permission system correctly applied readonly flag
- ✅ Idempotent operation (logs show "already exists" on re-apply)

### Production Status

**Fixed in:** Commit 6a86aad  
**Deployed:** 2025-11-22 02:10 UTC  
**Tested on:** Proxmox 9.1.1, container 502 (jellyfin-test)  
**Status:** ✅ Working in production
