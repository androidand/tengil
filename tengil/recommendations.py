"""
Container recommendations for different dataset types.

Provides suggestions for LXC containers that work well with specific
storage profiles and use cases.
"""

from rich.console import Console

# Container recommendations by dataset type
RECOMMENDATIONS = {
    "media": {
        "description": "Media streaming and management",
        "containers": [
            ("jellyfin", "Media server with transcoding, web UI, mobile apps"),
            ("plex", "Popular media server (proprietary but polished)"),
            ("emby", "Alternative media server"),
            ("kodi", "Media center application"),
        ],
        "supporting": [
            ("radarr", "Movie collection manager (downloads, renames)"),
            ("sonarr", "TV show collection manager"),
            ("bazarr", "Subtitle management for Radarr/Sonarr"),
            ("overseerr", "Request management for Plex/Jellyfin"),
        ]
    },
    "photos": {
        "description": "Photo backup, management, and AI processing",
        "containers": [
            ("immich", "Modern photo backup with AI face recognition, like Google Photos"),
            ("photoprism", "AI-powered photo management and search"),
            ("nextcloud", "Full cloud suite with photo management"),
            ("piwigo", "Web-based photo gallery"),
        ],
    },
    "downloads": {
        "description": "Download clients and automation",
        "containers": [
            ("qbittorrent", "BitTorrent client with web UI"),
            ("transmission", "Lightweight torrent client"),
            ("sabnzbd", "Usenet downloader"),
            ("nzbget", "Efficient usenet client"),
            ("prowlarr", "Indexer manager for *arr apps"),
        ],
    },
    "syncthing": {
        "description": "File synchronization across devices",
        "containers": [
            ("syncthing", "Continuous file synchronization (no cloud needed)"),
            ("resilio-sync", "Alternative sync solution (proprietary)"),
        ],
    },
    "backups": {
        "description": "Backup solutions",
        "containers": [
            ("duplicati", "Encrypted backups to cloud/local"),
            ("restic", "Fast, secure backup program"),
            ("borg", "Deduplicating backup program"),
            ("urbackup", "Client/server backup system"),
        ],
    },
    "documents": {
        "description": "Document management and collaboration",
        "containers": [
            ("nextcloud", "Full cloud suite (files, calendar, contacts)"),
            ("paperless-ngx", "Document management with OCR"),
            ("onlyoffice", "Office suite for Nextcloud"),
        ],
    },
    "ai": {
        "description": "AI and machine learning",
        "containers": [
            ("ollama", "Run LLMs locally (Llama, Mistral, etc.)"),
            ("stable-diffusion", "Image generation"),
            ("whisper", "Speech-to-text transcription"),
            ("comfyui", "Stable Diffusion workflow UI"),
        ],
    },
    "appdata": {
        "description": "Container management and monitoring",
        "containers": [
            ("portainer", "Docker/LXC container management UI"),
            ("dockge", "Docker compose stack manager"),
            ("yacht", "Container management interface"),
        ],
    },
}


def show_all_recommendations(console: Console):
    """Display overview of all container recommendations."""
    console.print("\n[cyan bold]Container Recommendations by Dataset Type[/cyan bold]\n")
    
    for dtype, rec in RECOMMENDATIONS.items():
        console.print(f"[bold]{dtype}[/bold] - {rec['description']}")
        containers = ", ".join([name for name, _ in rec['containers'][:3]])
        console.print(f"  → {containers}")
        if len(rec['containers']) > 3:
            console.print(f"  [dim]... and {len(rec['containers']) - 3} more[/dim]")
        console.print()
    
    console.print("[dim]Run 'tg suggest <type>' for detailed info[/dim]")


def show_dataset_recommendations(dataset_type: str, console: Console) -> bool:
    """Display detailed recommendations for a specific dataset type.
    
    Args:
        dataset_type: Type of dataset (media, photos, etc.)
        console: Rich console for output
        
    Returns:
        True if dataset type exists, False otherwise
    """
    if dataset_type not in RECOMMENDATIONS:
        console.print(f"[red]Unknown dataset type:[/red] {dataset_type}")
        console.print(f"\n[cyan]Available types:[/cyan] {', '.join(RECOMMENDATIONS.keys())}")
        return False
    
    rec = RECOMMENDATIONS[dataset_type]
    console.print(f"\n[cyan bold]{dataset_type.upper()}[/cyan bold]")
    console.print(f"[dim]{rec['description']}[/dim]\n")
    
    console.print("[cyan]Recommended containers:[/cyan]")
    for name, desc in rec['containers']:
        console.print(f"  [bold]{name:20s}[/bold] {desc}")
    
    if 'supporting' in rec:
        console.print("\n[cyan]Supporting tools:[/cyan]")
        for name, desc in rec['supporting']:
            console.print(f"  [bold]{name:20s}[/bold] {desc}")
    
    console.print("\n[dim]Install with Proxmox:[/dim]")
    console.print(f"  pct create <vmid> <template> --hostname {rec['containers'][0][0]}")
    console.print("\n[dim]Or use Proxmox web UI: Create CT → Select template[/dim]")
    
    return True
