"""
Discovery of available LXC templates and containers.

Queries Proxmox to find what container templates are available
and what containers already exist.
"""

from typing import List, Dict, Optional, Tuple
import subprocess
import json


class ProxmoxDiscovery:
    """Discover available LXC templates and existing containers on Proxmox."""
    
    def __init__(self, host: Optional[str] = None, user: str = "root"):
        """Initialize Proxmox discovery.
        
        Args:
            host: Proxmox host (IP or hostname). If None, runs locally.
            user: SSH user for remote host
        """
        self.host = host
        self.user = user
        self.is_local = host is None
    
    def _run_command(self, cmd: str) -> Tuple[bool, str]:
        """Run command locally or via SSH.
        
        Args:
            cmd: Command to run
            
        Returns:
            (success, output) tuple
        """
        if self.is_local:
            full_cmd = cmd
        else:
            full_cmd = f"ssh {self.user}@{self.host} '{cmd}'"
        
        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0, result.stdout
        except Exception as e:
            return False, str(e)
    
    def get_available_templates(self) -> List[Dict[str, str]]:
        """Get list of available LXC templates on Proxmox.
        
        Returns:
            List of dicts with template info: type, name
        """
        # Try to get available templates from remote repository
        success, output = self._run_command("pveam available")
        if not success:
            # Fall back to local templates
            success, output = self._run_command("pveam list local")
            if not success:
                return []
        
        templates = []
        for line in output.strip().split('\n'):
            if not line.strip():
                continue
            # Format: system          debian-12-standard_12.12-1_amd64.tar.zst
            parts = line.split(None, 1)
            if len(parts) >= 2:
                template_type = parts[0]
                template_name = parts[1].strip()
                templates.append({
                    'type': template_type,
                    'name': template_name
                })
        
        return templates
    
    def get_downloaded_templates(self) -> List[Dict[str, str]]:
        """Get list of already downloaded templates.
        
        Returns:
            List of dicts with template info: name, size
        """
        success, output = self._run_command("pveam list local")
        if not success:
            return []
        
        templates = []
        for line in output.strip().split('\n')[1:]:  # Skip header
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 2:
                templates.append({
                    'name': parts[0],
                    'size': parts[1] if len(parts) > 1 else 'unknown'
                })
        
        return templates
    
    def get_existing_containers(self) -> List[Dict[str, str]]:
        """Get list of existing LXC containers.
        
        Returns:
            List of dicts with container info: vmid, status, name
        """
        success, output = self._run_command("pct list")
        if not success:
            return []
        
        containers = []
        for line in output.strip().split('\n')[1:]:  # Skip header
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) >= 3:
                containers.append({
                    'vmid': parts[0],
                    'status': parts[1],
                    'name': parts[2]
                })
        
        return containers
    
    def search_template(self, pattern: str) -> List[Dict[str, str]]:
        """Search for templates matching a pattern.
        
        Args:
            pattern: Search pattern (e.g., 'debian', 'ubuntu', 'jellyfin')
            
        Returns:
            List of matching templates
        """
        templates = self.get_available_templates()
        pattern_lower = pattern.lower()
        return [
            t for t in templates 
            if pattern_lower in t['name'].lower()
        ]
    
    def get_template_info(self, template_name: str) -> Optional[Dict]:
        """Get detailed info about a specific template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Dict with template details or None if not found
        """
        templates = self.get_available_templates()
        for t in templates:
            if t['name'] == template_name:
                return t
        return None
    
    def download_template(self, template_name: str) -> bool:
        """Download a template to Proxmox.
        
        Args:
            template_name: Template to download (e.g., 'debian-12-standard')
            
        Returns:
            True if successful
        """
        success, output = self._run_command(f"pveam download local {template_name}")
        return success
