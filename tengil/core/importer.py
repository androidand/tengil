"""Import existing infrastructure into Tengil configuration."""
import re
import subprocess
from pathlib import Path
from typing import Dict, List

import yaml

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class InfrastructureImporter:
    """Scan existing system and generate tengil.yml."""
    
    def __init__(self, mock: bool = False):
        self.mock = mock
    
    def scan_zfs_pool(self, pool: str) -> Dict[str, Dict]:
        """Scan ZFS pool for existing datasets.
        
        Args:
            pool: Pool name to scan
            
        Returns:
            Dict of dataset_name -> properties
        """
        if self.mock:
            logger.info(f"MOCK: Would scan ZFS pool {pool}")
            return {
                'media': {
                    'compression': 'off',
                    'recordsize': '1M',
                    'atime': 'off',
                    'sync': 'standard',
                    'profile': 'media'
                }
            }
        
        try:
            cmd = ["zfs", "list", "-H", "-r", "-o", 
                   "name,compression,recordsize,atime,sync", pool]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            datasets = {}
            for line in result.stdout.splitlines():
                parts = line.split('\t')
                if len(parts) < 5:
                    continue
                    
                full_name = parts[0]
                # Skip the pool itself
                if full_name == pool:
                    continue
                
                # Get dataset name without pool prefix
                dataset_name = full_name.replace(f"{pool}/", "")
                
                datasets[dataset_name] = {
                    'compression': parts[1],
                    'recordsize': parts[2],
                    'atime': parts[3],
                    'sync': parts[4],
                    'profile': self._infer_profile(parts[1], parts[2])
                }
            
            return datasets
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to scan ZFS pool: {e}")
            return {}
    
    def _infer_profile(self, compression: str, recordsize: str) -> str:
        """Infer best profile based on properties."""
        # Media: large recordsize, no compression
        if recordsize == '1M' and compression == 'off':
            return 'media'
        
        # Backups: high compression
        if 'zstd' in compression:
            return 'backups'
        
        # Documents: compression + moderate recordsize
        if recordsize == '128K' and compression != 'off':
            return 'documents'
        
        # Default
        return 'media'
    
    def scan_container_mounts(self, vmid: int) -> List[Dict]:
        """Scan container for existing ZFS mounts.
        
        Args:
            vmid: Container ID
            
        Returns:
            List of mount configurations
        """
        if self.mock:
            logger.info(f"MOCK: Would scan container {vmid}")
            return []
        
        try:
            cmd = ["pct", "config", str(vmid)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            mounts = []
            for line in result.stdout.splitlines():
                if line.startswith('mp'):
                    # Parse: mp0: /tank/media,mp=/media,ro=1
                    match = re.search(r'mp\d+:\s*([^,]+),mp=([^,]+)', line)
                    if match:
                        host_path = match.group(1)
                        guest_path = match.group(2)
                        readonly = ',ro=1' in line
                        
                        mounts.append({
                            'host_path': host_path,
                            'mount': guest_path,
                            'readonly': readonly
                        })
            
            return mounts
            
        except subprocess.CalledProcessError:
            logger.warning(f"Could not scan container {vmid}")
            return []
    
    def get_container_config(self, vmid: int) -> Dict:
        """Get full container configuration from pct config.

        Args:
            vmid: Container ID

        Returns:
            Dict with container specs
        """
        if self.mock:
            return {
                'vmid': vmid,
                'hostname': f'container-{vmid}',
                'cores': 2,
                'memory': 2048,
                'rootfs': 'local-zfs:vm-100-disk-0,size=16G',
                'type': 'lxc',
                'ostype': 'debian'
            }

        try:
            cmd = ["pct", "config", str(vmid)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            config = {'vmid': vmid}
            env_vars = {}

            for line in result.stdout.splitlines():
                if ':' not in line:
                    continue

                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if key == 'hostname':
                    config['hostname'] = value
                elif key == 'cores':
                    config['cores'] = int(value)
                elif key == 'memory':
                    config['memory'] = int(value)
                elif key == 'rootfs':
                    config['rootfs'] = value
                    # Extract disk size
                    size_match = re.search(r'size=(\d+)G', value)
                    if size_match:
                        config['disk'] = int(size_match.group(1))
                elif key == 'ostype':
                    config['ostype'] = value
                elif key.startswith('mp'):
                    # Mount point handled separately
                    pass
                elif key.startswith('lxc.environment.'):
                    # Extract environment variable
                    var_name = key.replace('lxc.environment.', '')
                    env_vars[var_name] = value

            # Detect if this is an OCI container (has OCI rootfs or ostype markers)
            if 'rootfs' in config:
                rootfs = config['rootfs']
                # OCI containers typically have subvol in their rootfs
                if 'subvol' in rootfs or 'oci:' in rootfs.lower():
                    config['type'] = 'oci'
                    # Try to extract image name from ostype or comments
                    if 'ostype' in config and ':' in config.get('ostype', ''):
                        config['image'] = config['ostype']
                else:
                    config['type'] = 'lxc'
                    config['template'] = config.get('ostype', 'debian-12-standard')

            if env_vars:
                config['env'] = env_vars

            return config

        except subprocess.CalledProcessError:
            logger.warning(f"Could not get config for container {vmid}")
            return {'vmid': vmid}

    def list_containers(self) -> List[Dict]:
        """List all LXC containers.

        Returns:
            List of container info dicts
        """
        if self.mock:
            return [
                {'vmid': 100, 'name': 'jellyfin', 'status': 'running'},
                {'vmid': 101, 'name': 'plex', 'status': 'stopped'}
            ]

        try:
            cmd = ["pct", "list"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            containers = []
            for line in result.stdout.splitlines()[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    containers.append({
                        'vmid': int(parts[0]),
                        'name': parts[1] if len(parts) > 1 else f"ct-{parts[0]}",
                        'status': parts[2] if len(parts) > 2 else 'unknown'
                    })

            return containers

        except subprocess.CalledProcessError:
            logger.error("Could not list containers")
            return []
    
    def generate_config(self, pool: str, interactive: bool = True) -> Dict:
        """Generate complete tengil.yml from existing infrastructure.
        
        Args:
            pool: ZFS pool name
            interactive: Whether to prompt for selections
            
        Returns:
            Configuration dict ready to write as YAML
        """
        config = {
            'pools': {
                pool: {
                    'type': 'zfs',
                    'datasets': {}
                }
            }
        }
        
        # Scan ZFS datasets
        logger.info(f"Scanning ZFS pool: {pool}")
        zfs_datasets = self.scan_zfs_pool(pool)
        logger.info(f"Found {len(zfs_datasets)} dataset(s)")
        
        # For each dataset, check for container mounts
        containers = self.list_containers()
        logger.info(f"Found {len(containers)} container(s)")
        
        dataset_root = config['pools'][pool]['datasets']

        for dataset_name, props in zfs_datasets.items():
            dataset_config = {
                'profile': props['profile'],
                'zfs': {
                    'compression': props['compression'],
                    'recordsize': props['recordsize'],
                    'atime': props['atime'],
                    'sync': props['sync']
                }
            }
            
            # Check which containers mount this dataset
            dataset_containers = []
            for container in containers:
                mounts = self.scan_container_mounts(container['vmid'])
                for mount in mounts:
                    if dataset_name in mount['host_path']:
                        # Get full container config
                        ct_config = self.get_container_config(container['vmid'])

                        container_spec = {
                            'name': ct_config.get('hostname', container['name']),
                            'cores': ct_config.get('cores', 2),
                            'memory': ct_config.get('memory', 2048),
                            'disk': ct_config.get('disk', 16),
                            'auto_create': False  # Don't auto-create existing containers
                        }

                        # Add type-specific fields
                        if ct_config.get('type') == 'oci':
                            container_spec['type'] = 'oci'
                            if 'image' in ct_config:
                                container_spec['image'] = ct_config['image']
                        else:
                            container_spec['type'] = 'lxc'
                            if 'template' in ct_config:
                                container_spec['template'] = ct_config['template']

                        # Add environment variables if present
                        if 'env' in ct_config:
                            container_spec['env'] = ct_config['env']

                        # Add mounts
                        container_spec['mounts'] = [{
                            'source': mount['host_path'],
                            'target': mount['mount'],
                            'readonly': mount['readonly']
                        }]

                        dataset_containers.append(container_spec)
                        break  # Only add container once per dataset

            if dataset_containers:
                dataset_config['containers'] = dataset_containers

            dataset_root[dataset_name] = dataset_config

        return config
    
    def write_config(self, config: Dict, output_path: Path) -> bool:
        """Write configuration to YAML file.
        
        Args:
            config: Configuration dict
            output_path: Path to write to
            
        Returns:
            True if successful
        """
        try:
            with open(output_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Wrote configuration to: {output_path}")
            return True
            
        except OSError as e:
            logger.error(f"Failed to write config: {e}")
            return False
