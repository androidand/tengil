# Bugs Found During Full Deployment Testing
## Session: 22 November 2025

### Bug #1: State file not invalidated when config changes
**Severity:** High  
**Found:** When uploading new tengil.yml config  
**Symptom:** `tg diff` shows old/stale state even after fresh install  
**Workaround:** Manual `rm -rf .tengil/` required  
**Root Cause:** State store doesn't detect config file changes  
**Fix Needed:** 
- Add config file hash/timestamp to state.json
- Auto-invalidate state when config changes
- Add `--force-rescan` flag to diff/apply commands
- Show warning when state is older than config file

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
- **Fix Needed**: Better error handling - check if container exists after "failure"

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

---
*More bugs will be added as testing continues*
