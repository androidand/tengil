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
**TODO:** Add debug logging showing which config file was loaded and warn when multiple `tengil.yml` files exist.
