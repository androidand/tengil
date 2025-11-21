"""Tengil Core - Simplified architecture with zero bloat.

Single class that does everything. No abstraction layers, no delegation,
no unnecessary complexity. Just pure efficiency.
"""
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class PackageLoader:
    """Minimal package system - loads YAML packages and renders config."""
    
    def __init__(self):
        self.packages_dir = Path(__file__).parent / "packages"
    
    def list_packages(self) -> List[str]:
        """List available packages."""
        if not self.packages_dir.exists():
            return []
        return [f.stem for f in self.packages_dir.glob("*.yml")]
    
    def load_package(self, name: str) -> Dict[str, Any]:
        """Load package configuration."""
        package_file = self.packages_dir / f"{name}.yml"
        if not package_file.exists():
            raise FileNotFoundError(f"Package not found: {name}")
        
        return yaml.safe_load(package_file.read_text())
    
    def render_config(self, package_data: Dict[str, Any], pool: str = "tank") -> str:
        """Render package into tengil.yml config."""
        # Extract pools section or create basic structure
        if "pools" in package_data:
            config = package_data.copy()
            # Replace pool name if different
            if "tank" in config["pools"] and pool != "tank":
                config["pools"][pool] = config["pools"].pop("tank")
        else:
            # Create basic config from package metadata
            config = {
                "pools": {
                    pool: {
                        "datasets": {
                            "appdata": {
                                "profile": "appdata",
                                "containers": [
                                    {
                                        "name": package_data.get("name", "app"),
                                        "template": "debian-12-standard",
                                        "mount": "/data",
                                        "memory": 2048,
                                        "cores": 2
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        
        return yaml.dump(config, default_flow_style=False, sort_keys=False)


@dataclass
class ContainerSpec:
    """Container specification - minimal required fields only."""
    vmid: int
    name: str
    template: str
    memory: int = 2048
    cores: int = 2
    disk: str = "8G"
    privileged: bool = False
    startup_order: Optional[int] = None
    mount_path: Optional[str] = None
    host_path: Optional[str] = None
    readonly: bool = False
    post_install: Optional[List[str]] = None

    def __post_init__(self):
        if self.post_install is None:
            self.post_install = []


@dataclass
class OciAppSpec:
    """Declarative OCI/LXC app specification."""
    name: str
    image: str
    runtime: str = "oci"  # oci|lxc|docker-host
    dataset: str = "appdata"
    mount: str = "/data"
    env: Dict[str, Any] = None
    ports: List[Any] = None
    volumes: List[Any] = None

    def __post_init__(self):
        if self.env is None:
            self.env = {}
        if self.ports is None:
            self.ports = []
        if self.volumes is None:
            self.volumes = []


@dataclass
class ShareSpec:
    """Share specification - SMB or NFS."""
    type: str  # "smb" or "nfs"
    name: str
    path: str
    readonly: bool = False
    browseable: bool = True


@dataclass
class DatasetSpec:
    """Dataset specification - minimal required fields only."""
    pool: str
    name: str
    profile: str = "default"
    quota: Optional[str] = None
    containers: List[ContainerSpec] = None
    shares: List[ShareSpec] = None
    
    def __post_init__(self):
        if self.containers is None:
            self.containers = []
        if self.shares is None:
            self.shares = []


@dataclass
class Change:
    """A single change to be applied."""
    type: str  # "create_dataset", "create_container", "mount_container"
    target: str  # What's being changed
    spec: Any  # The specification
    
    def __str__(self) -> str:
        return f"{self.type}: {self.target}"


class Changes:
    """Collection of changes with formatting."""
    
    def __init__(self, changes: List[Change]):
        self.changes = changes
    
    def __len__(self) -> int:
        return len(self.changes)
    
    def __iter__(self):
        return iter(self.changes)
    
    def format(self) -> str:
        """Format changes for display."""
        if not self.changes:
            return "No changes needed"
        
        lines = [f"Plan: {len(self.changes)} changes"]
        for change in self.changes:
            lines.append(f"  + {change}")
        return "\n".join(lines)


class Config:
    """Unified configuration loader. No migrations, no smart defaults."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def load(cls, path: str) -> 'Config':
        """Load and validate configuration."""
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {path}")

        data = yaml.safe_load(config_path.read_text())
        if not data:
            raise ValueError("Empty configuration file")

        return cls(data)

    @classmethod
    def from_package(cls, package_name: str, pool: str = "tank") -> 'Config':
        """Load configuration from a package file."""
        # Look for package in tengil/packages/
        package_dir = Path(__file__).parent / "packages"
        package_file = package_dir / f"{package_name}.yml"

        if not package_file.exists():
            raise FileNotFoundError(f"Package not found: {package_name}")

        package_data = yaml.safe_load(package_file.read_text())

        # Extract pools section from package
        if "pools" in package_data:
            # Package has pools section - use it directly
            return cls(package_data)
        else:
            # Old format - construct minimal config
            return cls({"pools": {pool: {"datasets": {}}}})

    @classmethod
    def list_packages(cls) -> List[Dict[str, Any]]:
        """List available packages."""
        package_dir = Path(__file__).parent / "packages"
        if not package_dir.exists():
            return []

        packages = []
        for package_file in package_dir.glob("*.yml"):
            try:
                data = yaml.safe_load(package_file.read_text())
                packages.append({
                    "name": package_file.stem,
                    "description": data.get("description", "No description"),
                    "category": data.get("category", "general"),
                    "difficulty": data.get("difficulty", "intermediate")
                })
            except:
                pass

        return sorted(packages, key=lambda p: p["name"])

    @property
    def apps(self) -> List[OciAppSpec]:
        """Extract OCI/LXC app specifications (preferred runtime: OCI)."""
        app_specs: List[OciAppSpec] = []
        for app in self.data.get("apps", []) or []:
            # Allow simple string format "image" to default name from image
            if isinstance(app, str):
                image = app
                name = image.split("/")[-1].split(":")[0]
                app_specs.append(OciAppSpec(name=name, image=image))
                continue

            if not isinstance(app, dict):
                continue

            image = app.get("image")
            name = app.get("name") or (image.split("/")[-1].split(":")[0] if image else "app")
            runtime = app.get("runtime", "oci")

            app_specs.append(OciAppSpec(
                name=name,
                image=image,
                runtime=runtime,
                dataset=app.get("dataset", "appdata"),
                mount=app.get("mount", "/data"),
                env=app.get("env") or {},
                ports=app.get("ports") or [],
                volumes=app.get("volumes") or [],
            ))

        return app_specs
    
    @property
    def datasets(self) -> List[DatasetSpec]:
        """Extract dataset specifications."""
        datasets = []
        pools = self.data.get("pools", {})
        
        for pool_name, pool_config in pools.items():
            pool_datasets = pool_config.get("datasets", {})
            
            for dataset_name, dataset_config in pool_datasets.items():
                # Parse containers
                containers = []
                for container_config in dataset_config.get("containers", []):
                    if isinstance(container_config, str):
                        # Simple format: "name:/mount"
                        name, mount = container_config.split(":", 1)
                        containers.append(ContainerSpec(
                            vmid=0,  # Will be assigned
                            name=name.strip(),
                            template="debian-12-standard",
                            mount_path=mount.strip(),
                            host_path=f"/{pool_name}/{dataset_name}"
                        ))
                    elif isinstance(container_config, dict):
                        # Full format
                        # Parse post_install (can be string or list)
                        post_install = container_config.get("post_install")
                        if isinstance(post_install, str):
                            post_install = [post_install]
                        elif post_install is None:
                            post_install = []

                        containers.append(ContainerSpec(
                            vmid=container_config.get("vmid", 0),
                            name=container_config["name"],
                            template=container_config.get("template", "debian-12-standard"),
                            memory=container_config.get("memory", 2048),
                            cores=container_config.get("cores", 2),
                            disk=container_config.get("disk", "8G"),
                            privileged=container_config.get("privileged", False),
                            startup_order=container_config.get("startup_order"),
                            mount_path=container_config.get("mount"),
                            host_path=f"/{pool_name}/{dataset_name}",
                            readonly=container_config.get("readonly", False),
                            post_install=post_install
                        ))
                
                # Parse shares
                shares = []
                shares_config = dataset_config.get("shares", {})
                
                if "smb" in shares_config:
                    smb_config = shares_config["smb"]
                    if isinstance(smb_config, dict):
                        shares.append(ShareSpec(
                            type="smb",
                            name=smb_config.get("name", dataset_name.title()),
                            path=f"/{pool_name}/{dataset_name}",
                            readonly=smb_config.get("read only", "no") == "yes",
                            browseable=smb_config.get("browseable", "yes") == "yes"
                        ))
                
                if "nfs" in shares_config:
                    nfs_config = shares_config["nfs"]
                    if isinstance(nfs_config, (dict, bool)):
                        shares.append(ShareSpec(
                            type="nfs",
                            name=dataset_name,
                            path=f"/{pool_name}/{dataset_name}",
                            readonly=nfs_config.get("readonly", False) if isinstance(nfs_config, dict) else False
                        ))
                
                datasets.append(DatasetSpec(
                    pool=pool_name,
                    name=dataset_name,
                    profile=dataset_config.get("profile", "default"),
                    quota=dataset_config.get("quota"),
                    containers=containers,
                    shares=shares
                ))
        
        return datasets


class State:
    """Simple JSON state persistence."""
    
    def __init__(self, file_path: Path):
        self.file = file_path
        self._data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load state from file."""
        if not self.file.exists():
            return {"datasets": {}, "containers": {}}
        
        try:
            return json.loads(self.file.read_text())
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Corrupted state file {self.file}, starting fresh")
            return {"datasets": {}, "containers": {}}
    
    def _save(self) -> None:
        """Save state to file."""
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(self._data, indent=2))
    
    def has_dataset(self, pool: str, name: str) -> bool:
        """Check if dataset exists in state."""
        return f"{pool}/{name}" in self._data["datasets"]
    
    def has_container(self, vmid: int) -> bool:
        """Check if container exists in state."""
        return str(vmid) in self._data["containers"]
    
    def add_dataset(self, pool: str, name: str) -> None:
        """Record dataset creation."""
        self._data["datasets"][f"{pool}/{name}"] = {"created_by_tengil": True}
        self._save()
    
    def add_container(self, vmid: int, name: str) -> None:
        """Record container creation."""
        self._data["containers"][str(vmid)] = {"name": name, "created_by_tengil": True}
        self._save()


class ProxmoxAPI:
    """Direct Proxmox API calls. No abstraction layers."""
    
    def __init__(self, mock: bool = False):
        self.mock = mock
    
    def _run(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Execute command with optional mocking."""
        if self.mock:
            logger.info(f"MOCK: {' '.join(cmd)}")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    
    def dataset_exists(self, pool: str, name: str) -> bool:
        """Check if ZFS dataset exists."""
        if self.mock:
            # In mock mode, assume datasets don't exist
            return False
        result = self._run(["zfs", "list", f"{pool}/{name}"], check=False)
        return result.returncode == 0
    
    def create_dataset(self, spec: DatasetSpec) -> None:
        """Create ZFS dataset with profile properties."""
        dataset_path = f"{spec.pool}/{spec.name}"
        
        # Profile-based properties
        props = self._get_profile_properties(spec.profile)
        
        # Add quota if specified
        if spec.quota:
            props["quota"] = spec.quota
        
        # Build command
        cmd = ["zfs", "create"]
        for key, value in props.items():
            cmd.extend(["-o", f"{key}={value}"])
        cmd.append(dataset_path)
        
        self._run(cmd)
        logger.info(f"✓ Created dataset {dataset_path}")
    
    def _get_profile_properties(self, profile: str) -> Dict[str, str]:
        """Get ZFS properties for profile."""
        profiles = {
            "media": {
                "recordsize": "1M",
                "compression": "lz4",
                "atime": "off"
            },
            "appdata": {
                "recordsize": "128K", 
                "compression": "zstd",
                "atime": "off"
            },
            "dev": {
                "recordsize": "128K",
                "compression": "zstd-fast",
                "atime": "off"
            },
            "default": {
                "compression": "lz4",
                "atime": "off"
            }
        }
        return profiles.get(profile, profiles["default"])
    
    def container_exists(self, vmid: int) -> bool:
        """Check if container exists."""
        if self.mock:
            # In mock mode, assume containers don't exist
            return False
        result = self._run(["pct", "status", str(vmid)], check=False)
        return result.returncode == 0
    
    def get_next_vmid(self) -> int:
        """Get next available VMID."""
        if self.mock:
            return 100
        
        result = self._run(["pvesh", "get", "/cluster/nextid"])
        return int(result.stdout.strip())
    
    def create_container(self, spec: ContainerSpec) -> int:
        """Create LXC container."""
        if spec.vmid == 0:
            spec.vmid = self.get_next_vmid()
        
        cmd = [
            "pct", "create", str(spec.vmid),
            f"local:vztmpl/{spec.template}.tar.zst",
            "--hostname", spec.name,
            "--memory", str(spec.memory),
            "--cores", str(spec.cores),
            "--rootfs", f"local-lvm:{spec.disk}",
            "--onboot", "1"
        ]
        
        if spec.privileged:
            cmd.append("--privileged")
        
        if spec.startup_order:
            cmd.extend(["--startup", f"order={spec.startup_order}"])
        
        self._run(cmd)
        logger.info(f"✓ Created container {spec.name} (vmid={spec.vmid})")
        return spec.vmid
    
    def start_container(self, vmid: int) -> None:
        """Start container."""
        self._run(["pct", "start", str(vmid)])
        logger.info(f"✓ Started container {vmid}")
    
    def mount_dataset(self, vmid: int, host_path: str, container_path: str, readonly: bool = False) -> None:
        """Add bind mount to container."""
        # Get next mount point
        mp_num = self._get_next_mountpoint(vmid)
        
        # Build mount options
        options = "bind"
        if readonly:
            options += ",ro"
        
        cmd = [
            "pct", "set", str(vmid),
            f"--mp{mp_num}", f"{host_path},mp={container_path},{options}"
        ]
        
        self._run(cmd)
        logger.info(f"✓ Mounted {host_path} -> {container_path} (readonly={readonly})")
    
    def _get_next_mountpoint(self, vmid: int) -> int:
        """Get next available mount point number."""
        if self.mock:
            return 0

        result = self._run(["pct", "config", str(vmid)], check=False)
        if result.returncode != 0:
            return 0

        # Find highest mp number
        max_mp = -1
        for line in result.stdout.splitlines():
            if line.startswith("mp"):
                mp_num = int(line.split(":")[0][2:])
                max_mp = max(max_mp, mp_num)

        return max_mp + 1

    def run_post_install(self, vmid: int, tasks: List[str]) -> bool:
        """Run post-install tasks in container."""
        if not tasks:
            return True

        if self.mock:
            for task in tasks:
                logger.info(f"MOCK: Run post-install task '{task}' in container {vmid}")
            return True

        logger.info(f"Running {len(tasks)} post-install tasks in container {vmid}")

        # Wait for container to be ready
        import time
        time.sleep(5)

        for task in tasks:
            if not self._run_post_install_task(vmid, task):
                logger.error(f"Post-install task '{task}' failed")
                return False

        logger.info(f"✓ All post-install tasks completed for container {vmid}")
        return True

    def _run_post_install_task(self, vmid: int, task: str) -> bool:
        """Run a single post-install task."""
        # Built-in tasks
        if task == "docker":
            return self._install_docker(vmid)
        elif task == "portainer":
            return self._install_portainer(vmid)
        else:
            # Custom shell command
            return self._exec_in_container(vmid, task)

    def _install_docker(self, vmid: int) -> bool:
        """Install Docker in container."""
        logger.info(f"Installing Docker in container {vmid}...")

        install_script = """
        apt-get update
        apt-get install -y ca-certificates curl gnupg
        install -m 0755 -d /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        chmod a+r /etc/apt/keyrings/docker.gpg

        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list

        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        systemctl enable docker
        systemctl start docker
        """

        if self._exec_in_container(vmid, install_script):
            logger.info(f"✓ Docker installed in container {vmid}")
            return True
        else:
            logger.error(f"✗ Docker installation failed in container {vmid}")
            return False

    def _install_portainer(self, vmid: int) -> bool:
        """Install Portainer in container."""
        logger.info(f"Installing Portainer in container {vmid}...")

        install_script = """
        docker volume create portainer_data
        docker run -d \
          -p 9000:9000 \
          -p 9443:9443 \
          --name portainer \
          --restart=always \
          -v /var/run/docker.sock:/var/run/docker.sock \
          -v portainer_data:/data \
          portainer/portainer-ce:latest
        """

        if self._exec_in_container(vmid, install_script):
            # Get container IP
            ip = self._get_container_ip(vmid)
            logger.info(f"✓ Portainer installed in container {vmid}")
            if ip:
                logger.info(f"  Access Portainer at: http://{ip}:9000")
            return True
        else:
            logger.error(f"✗ Portainer installation failed in container {vmid}")
            return False

    def _exec_in_container(self, vmid: int, command: str) -> bool:
        """Execute command in container via pct exec."""
        try:
            result = subprocess.run(
                ['pct', 'exec', str(vmid), '--', 'bash', '-c', command],
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False

    def _get_container_ip(self, vmid: int) -> Optional[str]:
        """Get container IP address."""
        try:
            result = subprocess.run(
                ['pct', 'exec', str(vmid), '--', 'hostname', '-I'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Return first IP
                ips = result.stdout.strip().split()
                return ips[0] if ips else None
        except:
            pass
        return None
    
    def create_smb_share(self, spec: ShareSpec) -> None:
        """Create SMB share in /etc/samba/smb.conf."""
        if self.mock:
            logger.info(f"MOCK: Create SMB share {spec.name} -> {spec.path}")
            return
        
        # Read current smb.conf
        smb_conf = Path("/etc/samba/smb.conf")
        if smb_conf.exists():
            content = smb_conf.read_text()
        else:
            content = "[global]\n   workgroup = WORKGROUP\n   security = user\n\n"
        
        # Add share section
        share_section = f"""
[{spec.name}]
   path = {spec.path}
   browseable = {'yes' if spec.browseable else 'no'}
   read only = {'yes' if spec.readonly else 'no'}
   guest ok = no
   valid users = @users
"""
        
        # Check if share already exists
        if f"[{spec.name}]" not in content:
            content += share_section
            smb_conf.write_text(content)
            
            # Restart Samba
            self._run(["systemctl", "restart", "smbd"])
            logger.info(f"✓ Created SMB share {spec.name}")
    
    def create_nfs_share(self, spec: ShareSpec) -> None:
        """Create NFS export in /etc/exports."""
        if self.mock:
            logger.info(f"MOCK: Create NFS export {spec.path}")
            return
        
        exports_file = Path("/etc/exports")
        
        # Read current exports
        if exports_file.exists():
            content = exports_file.read_text()
        else:
            content = ""
        
        # Add export line
        options = "ro,sync,no_subtree_check" if spec.readonly else "rw,sync,no_subtree_check"
        export_line = f"{spec.path} *({options})\n"
        
        # Check if export already exists
        if spec.path not in content:
            content += export_line
            exports_file.write_text(content)
            
            # Reload exports
            self._run(["exportfs", "-ra"])
            logger.info(f"✓ Created NFS export {spec.path}")


class Tengil:
    """The core Tengil class. Does everything with zero bloat."""
    
    def __init__(self, config_path: str = "tengil.yml", mock: bool = False):
        self.config = Config.load(config_path)
        self.proxmox = ProxmoxAPI(mock=mock)
        self.state = State(Path(".tengil.state"))
        self.packages = PackageLoader()
    
    def diff(self) -> Changes:
        """Calculate what changes need to be made."""
        changes = []
        
        for dataset in self.config.datasets:
            # Check dataset
            dataset_exists = self.proxmox.dataset_exists(dataset.pool, dataset.name)
            if not dataset_exists and not self.state.has_dataset(dataset.pool, dataset.name):
                changes.append(Change(
                    type="create_dataset",
                    target=f"{dataset.pool}/{dataset.name}",
                    spec=dataset
                ))
            
            # Check containers
            for container in dataset.containers:
                if container.vmid == 0:
                    container.vmid = self.proxmox.get_next_vmid()
                
                container_exists = self.proxmox.container_exists(container.vmid)
                if not container_exists and not self.state.has_container(container.vmid):
                    changes.append(Change(
                        type="create_container", 
                        target=f"{container.name} (vmid={container.vmid})",
                        spec=container
                    ))
                
                # Add mount if container will exist and has mount config
                if container.mount_path and container.host_path:
                    if container_exists or not self.state.has_container(container.vmid):
                        changes.append(Change(
                            type="mount_dataset",
                            target=f"{container.host_path} -> {container.mount_path}",
                            spec=container
                        ))
            
            # Check shares
            for share in dataset.shares:
                # For simplicity, always add share changes (they're idempotent)
                changes.append(Change(
                    type=f"create_{share.type}_share",
                    target=f"{share.name} ({share.path})",
                    spec=share
                ))
        
        return Changes(changes)
    
    def apply(self, changes: Changes) -> Dict[str, int]:
        """Apply changes to Proxmox."""
        results = {"success": 0, "failed": 0}
        
        for change in changes:
            try:
                if change.type == "create_dataset":
                    self.proxmox.create_dataset(change.spec)
                    self.state.add_dataset(change.spec.pool, change.spec.name)
                
                elif change.type == "create_container":
                    vmid = self.proxmox.create_container(change.spec)
                    self.proxmox.start_container(vmid)
                    self.state.add_container(vmid, change.spec.name)

                    # Run post-install tasks if specified
                    if change.spec.post_install:
                        self.proxmox.run_post_install(vmid, change.spec.post_install)
                
                elif change.type == "mount_dataset":
                    self.proxmox.mount_dataset(
                        change.spec.vmid,
                        change.spec.host_path,
                        change.spec.mount_path,
                        change.spec.readonly
                    )
                
                elif change.type == "create_smb_share":
                    self.proxmox.create_smb_share(change.spec)
                
                elif change.type == "create_nfs_share":
                    self.proxmox.create_nfs_share(change.spec)
                
                results["success"] += 1
                
            except Exception as e:
                logger.error(f"Failed to apply {change}: {e}")
                results["failed"] += 1
        
        return results
