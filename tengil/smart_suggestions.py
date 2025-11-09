"""
Smart container matching - map app recommendations to actual available templates.

Combines our curated recommendations with what's actually available on Proxmox.
"""

from typing import Dict, List, Tuple, Optional
from rich.console import Console
from tengil.recommendations import RECOMMENDATIONS
from tengil.discovery import ProxmoxDiscovery


# Map recommended apps to template search patterns
APP_TO_TEMPLATE = {
    # Media
    "jellyfin": ["turnkey.*media", "debian.*standard", "ubuntu.*standard"],
    "plex": ["turnkey.*media", "debian.*standard", "ubuntu.*standard"],
    "emby": ["turnkey.*media", "debian.*standard", "ubuntu.*standard"],
    "radarr": ["debian.*standard", "ubuntu.*standard"],
    "sonarr": ["debian.*standard", "ubuntu.*standard"],
    
    # Photos
    "immich": ["debian.*standard", "ubuntu.*standard"],
    "photoprism": ["debian.*standard", "ubuntu.*standard"],
    "nextcloud": ["turnkey.*nextcloud", "debian.*standard", "ubuntu.*standard"],
    "piwigo": ["turnkey.*gallery", "debian.*standard"],
    
    # Downloads
    "qbittorrent": ["debian.*standard", "ubuntu.*standard"],
    "transmission": ["turnkey.*torrent", "debian.*standard"],
    "sabnzbd": ["debian.*standard", "ubuntu.*standard"],
    
    # Syncthing
    "syncthing": ["debian.*standard", "ubuntu.*standard"],
    
    # Backups
    "duplicati": ["debian.*standard", "ubuntu.*standard"],
    "urbackup": ["turnkey.*backup", "debian.*standard"],
    
    # Documents
    "paperless-ngx": ["debian.*standard", "ubuntu.*standard"],
    "onlyoffice": ["debian.*standard", "ubuntu.*standard"],
    
    # AI
    "ollama": ["debian.*standard", "ubuntu.*standard"],
    "stable-diffusion": ["ubuntu.*standard"],
    
    # Management
    "portainer": ["debian.*standard", "ubuntu.*standard"],
}

# Installation commands for apps (to run after CT creation)
INSTALL_COMMANDS = {
    "jellyfin": [
        "apt update && apt install -y curl gnupg",
        "curl -fsSL https://repo.jellyfin.org/install-debuntu.sh | bash",
    ],
    "nextcloud": [
        "apt update && apt install -y apache2 mariadb-server php php-{mysql,curl,gd,mbstring,xml,zip,imagick}",
        "wget https://download.nextcloud.com/server/releases/latest.tar.bz2",
        "tar -xjf latest.tar.bz2 -C /var/www/html/",
    ],
    "immich": [
        "apt update && apt install -y docker.io docker-compose",
        "mkdir -p /opt/immich && cd /opt/immich",
        "wget https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml",
        "docker-compose up -d",
    ],
    "ollama": [
        "curl -fsSL https://ollama.com/install.sh | sh",
    ],
    "portainer": [
        "apt update && apt install -y docker.io",
        "docker volume create portainer_data",
        "docker run -d -p 9000:9000 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce",
    ],
}


class SmartContainerMatcher:
    """Match recommended apps to available Proxmox templates."""
    
    def __init__(self, discovery: ProxmoxDiscovery, console: Console = None):
        self.discovery = discovery
        self.console = console or Console()
    
    def suggest_for_dataset(self, dataset_type: str) -> Dict:
        """Get smart suggestions for a dataset type.
        
        Args:
            dataset_type: Type (media, photos, etc.)
            
        Returns:
            Dict with apps, templates, and install commands
        """
        if dataset_type not in RECOMMENDATIONS:
            return {}
        
        rec = RECOMMENDATIONS[dataset_type]
        available_templates = self.discovery.get_available_templates()
        
        suggestions = []
        for app_name, app_desc in rec['containers']:
            # Find matching template
            template = self._find_best_template(app_name, available_templates)
            
            suggestion = {
                'app': app_name,
                'description': app_desc,
                'template': template,
                'install_commands': INSTALL_COMMANDS.get(app_name, []),
            }
            suggestions.append(suggestion)
        
        return {
            'dataset_type': dataset_type,
            'description': rec['description'],
            'suggestions': suggestions,
        }
    
    def _find_best_template(self, app_name: str, templates: List[Dict]) -> Optional[str]:
        """Find the best matching template for an app.
        
        Args:
            app_name: Name of the app
            templates: Available templates from Proxmox
            
        Returns:
            Template name or None
        """
        import re
        
        patterns = APP_TO_TEMPLATE.get(app_name, ["debian.*standard"])
        
        # Try each pattern in order of preference
        for pattern in patterns:
            for template in templates:
                template_name = template['name']
                if re.search(pattern, template_name, re.IGNORECASE):
                    return template_name
        
        # Fallback: latest debian standard
        for template in templates:
            if 'debian' in template['name'] and 'standard' in template['name']:
                return template['name']
        
        return None
    
    def show_smart_suggestions(self, dataset_type: str):
        """Display smart suggestions with matched templates."""
        result = self.suggest_for_dataset(dataset_type)
        if not result:
            self.console.print(f"[red]Unknown dataset type:[/red] {dataset_type}")
            return False
        
        self.console.print(f"\n[cyan bold]{dataset_type.upper()}[/cyan bold]")
        self.console.print(f"[dim]{result['description']}[/dim]\n")
        
        for sug in result['suggestions']:
            self.console.print(f"[bold cyan]→ {sug['app']}[/bold cyan]")
            self.console.print(f"  {sug['description']}")
            
            if sug['template']:
                self.console.print(f"  [green]✓ Template available:[/green] {sug['template']}")
                self.console.print(f"    [dim]pct create <vmid> local:vztmpl/{sug['template']} --hostname {sug['app']}[/dim]")
            else:
                self.console.print(f"  [yellow]⚠ No pre-built template. Use debian-12-standard and install manually[/yellow]")
            
            if sug['install_commands']:
                self.console.print(f"  [dim]Post-install commands:[/dim]")
                for cmd in sug['install_commands'][:2]:  # Show first 2
                    self.console.print(f"    [dim]{cmd}[/dim]")
                if len(sug['install_commands']) > 2:
                    self.console.print(f"    [dim]... and {len(sug['install_commands']) - 2} more[/dim]")
            
            self.console.print()
        
        return True
    
    def generate_install_script(self, dataset_type: str, apps: List[str]) -> str:
        """Generate a complete installation script.
        
        Args:
            dataset_type: Dataset type
            apps: List of apps to install
            
        Returns:
            Bash script content
        """
        result = self.suggest_for_dataset(dataset_type)
        if not result:
            return ""
        
        script_lines = [
            "#!/usr/bin/env bash",
            f"# Installation script for {dataset_type} apps",
            "# Generated by Tengil",
            "",
            "set -e",
            "",
        ]
        
        vmid = 100
        for sug in result['suggestions']:
            if sug['app'] not in apps:
                continue
            
            template = sug['template'] or 'debian-12-standard_12.12-1_amd64.tar.zst'
            
            script_lines.extend([
                f"# Install {sug['app']}",
                f"echo 'Creating container for {sug['app']}...'",
                f"pct create {vmid} local:vztmpl/{template} \\",
                f"  --hostname {sug['app']} \\",
                f"  --memory 2048 \\",
                f"  --cores 2 \\",
                f"  --net0 name=eth0,bridge=vmbr0,ip=dhcp \\",
                f"  --storage local-lvm",
                f"pct start {vmid}",
                "",
            ])
            
            if sug['install_commands']:
                script_lines.append(f"# Configure {sug['app']}")
                for cmd in sug['install_commands']:
                    script_lines.append(f"pct exec {vmid} -- bash -c '{cmd}'")
                script_lines.append("")
            
            vmid += 1
        
        return "\n".join(script_lines)
