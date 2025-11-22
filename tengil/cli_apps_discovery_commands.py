"""Apps discovery CLI commands - find running services with IPs and ports."""
import subprocess
from typing import Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from tengil.services.proxmox.containers.discovery import ContainerDiscovery

AppsTyper = typer.Typer(help="Discover and list running applications")


def register_apps_commands(root: typer.Typer, console: Console) -> None:
    """Attach apps discovery commands to the main CLI."""

    @AppsTyper.command("list")
    def list_apps(
        format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, urls"),
        container: Optional[str] = typer.Option(None, "--container", "-c", help="Filter by container name"),
        mock: bool = typer.Option(False, "--mock", help="Run in mock mode (no Proxmox required)"),
    ) -> None:
        """List all running applications with IPs and access URLs.
        
        Discovers services running in containers by scanning:
        - Jellyfin (port 8096)
        - Portainer (port 9000)
        - Immich (port 2283)
        - Syncthing (port 8384)
        - Home Assistant (port 8123)
        - Home Assistant MCP (port 3000)
        - Custom Docker containers (exposed ports)
        """
        discovery = ContainerDiscovery(mock=mock)
        containers = discovery.list_containers()
        
        # Filter if requested
        if container:
            containers = [c for c in containers if container.lower() in c['name'].lower()]
        
        apps = []
        for ct in containers:
            if ct['status'] != 'running':
                continue
            
            vmid = ct['vmid']
            name = ct['name']
            
            # Get container IP
            ip = _get_container_ip(vmid, mock=mock)
            if not ip:
                continue
            
            # Detect services
            services = _detect_services(vmid, ip)
            
            if services:
                for service in services:
                    apps.append({
                        'container': name,
                        'vmid': vmid,
                        'ip': ip,
                        'service': service['name'],
                        'port': service['port'],
                        'url': service['url'],
                        'description': service['description']
                    })
        
        if not apps:
            console.print("[yellow]No running applications detected[/yellow]")
            console.print("\n[dim]Tip: Applications must be running and have network access[/dim]")
            return
        
        # Output in requested format
        if format == "json":
            import json
            console.print(json.dumps(apps, indent=2))
        elif format == "urls":
            console.print("\n[bold cyan]Access URLs:[/bold cyan]\n")
            for app in apps:
                console.print(f"  {app['service']:20} {app['url']}")
        else:
            _display_apps_table(console, apps)
    
    @AppsTyper.command("open")
    def open_app(
        service: str = typer.Argument(..., help="Service name (jellyfin, portainer, immich, etc)"),
    ) -> None:
        """Open application URL in browser.
        
        Example: tg apps open jellyfin
        """
        discovery = ContainerDiscovery(mock=False)
        containers = discovery.list_containers()
        
        # Search for service
        for ct in containers:
            if ct['status'] != 'running':
                continue
            
            vmid = ct['vmid']
            ip = _get_container_ip(vmid)
            if not ip:
                continue
            
            services = _detect_services(vmid, ip)
            for svc in services:
                if service.lower() in svc['name'].lower():
                    console.print(f"[green]Opening {svc['name']} at {svc['url']}[/green]")
                    subprocess.run(['open', svc['url']], check=False)  # macOS
                    return
        
        console.print(f"[red]Service '{service}' not found[/red]")
        console.print("\n[dim]Run 'tg apps list' to see available services[/dim]")
    
    # Register the command group
    root.add_typer(AppsTyper, name="apps")


def _get_container_ip(vmid: int, mock: bool = False) -> Optional[str]:
    """Get IP address of a container."""
    if mock:
        return "192.168.1.100"

    try:
        result = subprocess.run(
            ['pct', 'exec', str(vmid), '--', 'hostname', '-I'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split()[0]
    except Exception:
        pass
    return None


def _detect_services(vmid: int, ip: str) -> List[Dict[str, str]]:
    """Detect running services in a container.
    
    Args:
        vmid: Container ID
        ip: Container IP address
        
    Returns:
        List of detected services with name, port, url, description
    """
    services = []
    
    # Known service ports to check
    service_checks = [
        {'name': 'Jellyfin', 'port': 8096, 'description': 'Media server', 'path': ''},
        {'name': 'Portainer', 'port': 9000, 'description': 'Docker management', 'path': ''},
        {'name': 'Immich', 'port': 2283, 'description': 'Photo backup', 'path': ''},
        {'name': 'Syncthing', 'port': 8384, 'description': 'File sync', 'path': ''},
        {'name': 'Home Assistant', 'port': 8123, 'description': 'Smart home', 'path': ''},
        {'name': 'HA-MCP', 'port': 3000, 'description': 'Home Assistant MCP', 'path': '/health'},
        {'name': 'Plex', 'port': 32400, 'description': 'Media server', 'path': '/web'},
        {'name': 'Nextcloud', 'port': 80, 'description': 'Cloud storage', 'path': ''},
        {'name': 'Pi-hole', 'port': 80, 'description': 'Ad blocker', 'path': '/admin'},
        {'name': 'Nginx', 'port': 80, 'description': 'Web server', 'path': ''},
        {'name': 'Nginx', 'port': 443, 'description': 'Web server (HTTPS)', 'path': ''},
    ]
    
    for check in service_checks:
        if _check_port(ip, check['port']):
            services.append({
                'name': check['name'],
                'port': check['port'],
                'url': f"http://{ip}:{check['port']}{check['path']}",
                'description': check['description']
            })
    
    # Check for custom Docker ports
    docker_ports = _get_docker_ports(vmid)
    for port_info in docker_ports:
        services.append({
            'name': port_info['container'],
            'port': port_info['port'],
            'url': f"http://{ip}:{port_info['port']}",
            'description': f"Docker: {port_info['image']}"
        })
    
    return services


def _check_port(ip: str, port: int) -> bool:
    """Check if a port is open."""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _get_docker_ports(vmid: int) -> List[Dict[str, any]]:
    """Get exposed Docker container ports.
    
    Args:
        vmid: LXC container ID
        
    Returns:
        List of dicts with container name, image, and port
    """
    try:
        # Check if Docker is running
        result = subprocess.run(
            ['pct', 'exec', str(vmid), '--', 'which', 'docker'],
            capture_output=True,
            timeout=2
        )
        if result.returncode != 0:
            return []
        
        # Get Docker PS output with ports
        result = subprocess.run(
            ['pct', 'exec', str(vmid), '--', 'docker', 'ps', '--format', '{{.Names}}|{{.Image}}|{{.Ports}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return []
        
        ports_list = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('|')
            if len(parts) < 3:
                continue
            
            container_name = parts[0]
            image = parts[1].split(':')[0]  # Remove tag
            ports_str = parts[2]
            
            # Parse ports like "0.0.0.0:8080->80/tcp"
            import re
            port_matches = re.findall(r'0\.0\.0\.0:(\d+)->', ports_str)
            for port in port_matches:
                # Skip already known services
                if int(port) in [8096, 9000, 2283, 8384, 8123, 3000]:
                    continue
                
                ports_list.append({
                    'container': container_name,
                    'image': image,
                    'port': int(port)
                })
        
        return ports_list
        
    except Exception:
        return []


def _display_apps_table(console: Console, apps: List[Dict]) -> None:
    """Display apps in a formatted table."""
    table = Table(title="Running Applications", show_header=True, header_style="bold cyan")
    
    table.add_column("Container", style="yellow")
    table.add_column("Service", style="green")
    table.add_column("Description", style="dim")
    table.add_column("Access URL", style="blue")
    
    for app in apps:
        table.add_row(
            app['container'],
            app['service'],
            app['description'],
            app['url']
        )
    
    console.print()
    console.print(table)
    console.print()
    console.print("[dim]Tip: Use 'tg apps open <service>' to open in browser[/dim]")
    console.print("[dim]     Use 'tg apps list --format urls' for copy-paste URLs[/dim]")
