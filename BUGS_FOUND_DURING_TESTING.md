# Bugs Found During Full Deployment Testing
## Session: 22 November 2025

### Bug #1: State file not invalidated when config changes
**Severity:** High  
**Status:** ✅ Fixed  
**Fix:** StateStore now fingerprints `tengil.yml` and auto-invalidates cached state when the config changes. Default config path follows the state location to avoid cwd issues.

### Bug #2: MOCK mode appearing in diff output
**Severity:** Medium  
**Found:** Running `tg diff` shows "MOCK: Would list datasets"  
**Symptom:** Logs show MOCK operations even on real server  
**Investigation Needed:** Why is mock mode enabled by default?

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
**Symptom:** `tg scan` only captures reality snapshot but doesn't load the desired config from tengil.yml into state.json. This means diff/apply run after scan will think there's no desired state and report "infrastructure up to date" even when new containers should be created.

**Workaround:** Don't use scan standalone - run diff or apply which load both reality AND desired config.

**Root Cause:** scan command doesn't accept --config flag and doesn't load desired state, only captures reality. This breaks the workflow of "scan then diff then apply".

**Expected:** scan should load desired config alongside reality snapshot so state.json has both.

### Bug #7: Config format confusion - `backend:` vs `type:` for OCI containers
**Severity:** Medium (Documentation)  
**Symptom:** Created configs using `backend: oci` which doesn't work. The correct syntax is `type: oci` with an `oci:` section containing `image:`, `tag:`, `registry:` fields.

**Root Cause:** Inconsistent terminology - some parts of code use "backend" but the config schema uses "type".

**Expected:** Documentation should clearly show that OCI containers require:
```yaml
type: oci
oci:
  image: nginx
  tag: alpine
  registry: docker.io
```

Not `backend: oci`.

### Bug #8: Config schema mismatch - OCI containers need top-level `image` field
**Severity:** High (Config Format)  
**Status:** ✅ Documented  
**Found:** Trying to use `type: oci` with nested `oci: image: nginx`  
**Symptom:** Error: "auto_create requires 'template' field (LXC) or 'image' field (OCI)"  
**Root Cause:** The container orchestrator expects OCI image as a top-level `image` field, not nested under `oci:`. Example file `test-oci-auto.yml` shows nested format but code doesn't support it.

**Working Format:**
```yaml
containers:
  - name: nginx-test
    type: oci
    image: nginx:alpine  # Top-level field
    auto_create: true
```

**Non-Working Format:**
```yaml
containers:
  - name: nginx-test
    type: oci
    auto_create: true
    oci:  # Nested - NOT supported by code
      image: nginx
      tag: alpine
```

**Fix:** Use top-level `image: nginx:alpine` field. The code splits on `:` to extract tag.

---

## Bug #9: YAML Boolean Conversion for ZFS Properties

**Status:** ⚠️ CRITICAL - Blocks use of valid ZFS property values

**Severity:** High - Prevents setting common ZFS properties

**Impact:** Cannot disable atime or compression using valid ZFS values

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

### Proper Fix Required

Need to add boolean-to-string conversion in one of these places:

1. **Config Loader** (`config_loader.py`): Convert booleans to ZFS strings immediately after YAML parsing
2. **Profile Applicator**: Handle boolean conversion when applying profiles
3. **ZFS Manager** (`zfs_manager.py`): Convert booleans before command construction

**Recommended approach:**
```python
# In config_loader.py or profile applicator
ZFS_BOOLEAN_MAP = {
    True: 'on',
    False: 'off'
}

def normalize_zfs_property(key: str, value: Any) -> str:
    if isinstance(value, bool):
        return ZFS_BOOLEAN_MAP[value]
    return str(value)
```

### Current Workaround

Avoid YAML boolean keywords entirely:
- Use `lz4` instead of `off` for compression
- Accept `atime=on` (minor performance cost) instead of fighting YAML parser

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
