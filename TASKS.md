# Tengil Development Tasks

## Active Tasks

### 🔥 High Priority - Docker Setup Improvements

- [ ] **Add `requires_docker` flag support** (lifecycle.py)
  - After container creation, check for `requires_docker` flag
  - Append `lxc.apparmor.profile: unconfined` to `/etc/pve/lxc/{vmid}.conf`
  - Add `keyctl=1` to features for better Docker support
  
- [ ] **Update docker-host package** (packages/docker-host.yml)
  - Add `requires_docker: true` to container spec
  - Add `post_install: [docker, portainer]` to container spec
  - Test that one `tg apply` creates working Docker host
  
- [ ] **Show container IP in output** (orchestrator.py)
  - After container started, get IP with `pct exec {vmid} -- hostname -I`
  - Log container IP clearly
  - If Portainer installed, show access URL

### 🚀 Medium Priority - UX Improvements

- [ ] **Pre-flight validation** (cli_state_commands.py)
  - Check storage exists before apply
  - Warn about missing templates
  - Validate sufficient host resources
  - Show clear errors with suggestions

- [ ] **Better error messages**
  - Catch common Proxmox API errors
  - Suggest fixes for storage/template issues
  - Link to troubleshooting docs

### 📚 Low Priority - Git Integration

- [ ] **Add `tg git` command group** (cli_git_commands.py)
  - `tg git init [--repo URL]` - Initialize git for config
  - `tg git status` - Show config git status
  - `tg git commit -m "msg"` - Commit tengil.yml changes
  - `tg git push` - Push to remote

- [ ] **Post-apply git hints** (cli_state_commands.py)
  - Check if in git repo after successful apply
  - If uncommitted changes, suggest commit command
  - Keep hints brief and non-intrusive

### 🔄 Future - Drift Management

- [ ] **`tg import-drift` command** (cli_drift_commands.py)
  - Calculate drift between tengil.yml and reality
  - Show what changed in GUI
  - Prompt to update tengil.yml with reality state
  - Save updated config

- [ ] **Interactive drift resolution**
  - Show drift item by item
  - Let user choose: keep tengil.yml or accept reality
  - Update config with accepted changes

## Completed ✅

- [x] Fix container auto-creation (container_changes parameter)
- [x] Fix privileged container creation (--unprivileged 0/1)
- [x] Fix disk size format for ZFS (strip unit suffix)
- [x] Separate template storage from rootfs storage
- [x] Create docker-host package

## Testing Checklist

### Docker Host Setup Test
```bash
cd /tmp/tengil-test
tg init --package docker-host
# Verify post_install and requires_docker in generated config
tg apply
# Should see:
# ✓ Container created
# ✓ Docker installed
# ✓ Portainer installed
# ✓ Container IP: 192.168.1.X
# Access Portainer at http://192.168.1.X:9000
```

### Git Workflow Test
```bash
cd /tmp/tengil-test
echo "version: 2" > tengil.yml
tg git init
git status  # Should show tengil.yml
tg git commit -m "test"
# Should commit successfully
```

## Notes

- Post-install infrastructure already exists in `tengil/services/post_install.py`
- Container orchestrator already calls post_install if specified in config
- Main gap: we didn't include `post_install` in our test config
- AppArmor issue requires manual config edit - need to automate

## Ideas for Future

- Auto-detect best storage (largest ZFS pool)
- Package repository/marketplace
- Template auto-download with progress bar
- Container resource recommendations based on package
- Web UI for tengil.yml editing
- VS Code extension for tengil.yml
