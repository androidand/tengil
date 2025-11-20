"""Smart permission inference helpers.

Provides simple defaults based on container naming patterns, dataset
profiles, and explicit overrides.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tengil.core.logger import get_logger

logger = get_logger(__name__)

# Known container patterns that imply readonly mounts 🌈
READONLY_CONTAINERS = {
    # Media servers - they just serve, don't write
    "jellyfin", "plex", "emby", "kodi", "jellyseerr",
    "tautulli", "overseerr", "ombi",
    
    # Photo/music servers - read-only viewers
    "photoprism", "immich-server", "immich-web",
    "navidrome", "airsonic", "funkwhale",
    
    # Static content servers
    "nginx", "apache", "caddy", "traefik",
    "hugo", "jekyll", "gatsby",
    
    # Monitoring/dashboards - read metrics, don't write data
    "grafana", "prometheus", "node-exporter",
    "uptime-kuma", "heimdall", "homer",
}

# Known container patterns that imply readwrite mounts 🦄
READWRITE_CONTAINERS = {
    # *arr stack - download and organize media
    "sonarr", "radarr", "lidarr", "prowlarr", "bazarr",
    "readarr", "whisparr", "mylar3",
    
    # Download clients - write downloaded files
    "qbittorrent", "transmission", "deluge", "sabnzbd",
    "nzbget", "rtorrent", "flood",
    
    # File sync/storage - need write access
    "nextcloud", "syncthing", "seafile",
    "filebrowser", "duplicati", "restic",
    
    # Photo management - import/organize photos
    "immich", "photoprism-import", "photostructure",
    
    # Development/admin tools - need to write configs
    "portainer", "code-server", "gitea", "gitlab",
    "jenkins", "drone", "woodpecker",
    
    # Databases - obviously need write access
    "postgres", "mysql", "mariadb", "mongodb",
    "redis", "influxdb", "elasticsearch",
    
    # Home automation - write state/configs
    "homeassistant", "nodered", "zigbee2mqtt",
    "mosquitto", "openhab", "domoticz",
}


@dataclass
class SmartPermissionEvent:
    """Telemetry emitted while inferring permissions."""

    type: str
    container: str
    pattern: str
    access: str
    dataset: Optional[str] = None
    exact: bool = True


def _match_known_container(name: str) -> Optional[Tuple[bool, str, bool]]:
    """Return (readonly, pattern, exact) if the name matches a known rule."""

    name_lower = name.lower()

    # Exact matches first
    if name_lower in READONLY_CONTAINERS:
        return True, name_lower, True
    if name_lower in READWRITE_CONTAINERS:
        return False, name_lower, True

    # Context-aware fuzzy matching 🦄
    # Some patterns need context to determine intent
    
    # nginx-proxy, nginx-config = readwrite (proxy/config management)
    # nginx-static, nginx-serve = readonly (static content serving)
    if 'nginx' in name_lower:
        if any(keyword in name_lower for keyword in ['proxy', 'config', 'admin', 'manager']):
            return False, 'nginx-proxy', False
        else:
            return True, 'nginx', False
    
    # Standard fuzzy matching for other patterns
    for pattern in READONLY_CONTAINERS:
        if name_lower.startswith(pattern) or pattern in name_lower:
            return True, pattern, False

    for pattern in READWRITE_CONTAINERS:
        if name_lower.startswith(pattern) or pattern in name_lower:
            return False, pattern, False

    return None


def infer_container_access(
    container_name: str,
    dataset_profile: Optional[str],
    *,
    dataset: Optional[str] = None,
    events: Optional[List[SmartPermissionEvent]] = None,
) -> bool:
    """Infer readonly flag for a container."""

    if not container_name:
        return True

    match = _match_known_container(container_name)
    access_label: Dict[bool, str] = {True: "readonly", False: "readwrite"}

    if match is not None:
        readonly, pattern, exact = match
        if not exact:
            message = (
                f"Fuzzy matched container '{container_name}' to pattern '{pattern}' -> "
                f"{access_label[readonly]}"
            )
            logger.info(message)
            if events is not None:
                events.append(
                    SmartPermissionEvent(
                        type="fuzzy-match",
                        container=container_name,
                        pattern=pattern,
                        access=access_label[readonly],
                        dataset=dataset,
                        exact=False,
                    )
                )
        return readonly

    # Profile-based fallbacks (the unicorn's backup plan) 🦄
    profile = (dataset_profile or "default").lower()
    
    profile_defaults = {
        "media": True,      # Media = readonly (serve content)
        "photos": True,     # Photos = readonly (view photos)
        "documents": True,  # Documents = readonly (view docs)
        "backups": True,    # Backups = readonly (restore only)
        "appdata": False,   # App data = readwrite (apps need to write)
        "dev": False,       # Development = readwrite (code changes)
        "downloads": False, # Downloads = readwrite (write files)
    }
    
    return profile_defaults.get(profile, True)  # Conservative default


def infer_dataset_permissions(
    containers: Sequence[Dict[str, Any]],
    profile: Optional[str],
    *,
    dataset: Optional[str] = None,
    events: Optional[List[SmartPermissionEvent]] = None,
) -> str:
    """Infer dataset-level permission mask (e.g. 755 vs 775)."""

    has_writers = False

    for container in containers:
        if not isinstance(container, dict):
            continue

        explicit = container.get("readonly")
        if explicit is False:
            has_writers = True
            continue

        if explicit is None:
            inferred = infer_container_access(
                container.get("name", ""),
                profile,
                dataset=dataset,
                events=events,
            )
            if not inferred:
                has_writers = True

    return "775" if has_writers else "755"


def infer_smb_permissions(
    containers: Sequence[Dict[str, Any]],
    profile: Optional[str],
    *,
    dataset: Optional[str] = None,
    events: Optional[List[SmartPermissionEvent]] = None,
) -> Dict[str, str]:
    """Infer SMB read/write flags from container usage."""

    has_writers = False

    for container in containers:
        if not isinstance(container, dict):
            continue

        explicit = container.get("readonly")
        if explicit is False:
            has_writers = True
            continue

        if explicit is None and not infer_container_access(
            container.get("name", ""),
            profile,
            dataset=dataset,
            events=events,
        ):
            has_writers = True

    if has_writers:
        return {"read only": "no", "writable": "yes"}

    return {"read only": "yes", "writable": "no"}


def apply_smart_defaults(
    dataset_config: Dict[str, Any],
    dataset_name: str,
    *,
    events: Optional[List[SmartPermissionEvent]] = None,
) -> Dict[str, Any]:
    """Apply container/share defaults based on smart inference."""

    profile = dataset_config.get("profile")
    containers = dataset_config.get("containers") or []

    for container in containers:
        if not isinstance(container, dict):
            continue
        if "readonly" in container:
            continue

        inferred_readonly = infer_container_access(
            container.get("name", ""),
            profile,
            dataset=dataset_name,
            events=events,
        )
        
        # Only set readonly flag if it's True (readonly)
        # Don't set it if it's False (readwrite) since that's the default
        if inferred_readonly:
            container["readonly"] = True

    if "shares" in dataset_config and isinstance(dataset_config["shares"], dict):
        shares = dataset_config["shares"]
        if "smb" in shares:
            smb_entries = shares["smb"]
            inferred = infer_smb_permissions(
                containers,
                profile,
                dataset=dataset_name,
                events=events,
            )

            if isinstance(smb_entries, dict):
                for key, value in inferred.items():
                    smb_entries.setdefault(key, value)
            elif isinstance(smb_entries, list):
                for entry in smb_entries:
                    if isinstance(entry, dict):
                        for key, value in inferred.items():
                            entry.setdefault(key, value)

    return dataset_config


def validate_permissions(dataset_config: Dict[str, Any], dataset_name: str) -> List[str]:
    """Validate permission consistency and produce warnings."""

    containers = dataset_config.get("containers") or []
    profile = dataset_config.get("profile")
    warnings: List[str] = []
    
    readonly_containers: List[str] = []
    readwrite_containers: List[str] = []
    profile_mismatches: List[str] = []

    for container in containers:
        if not isinstance(container, dict):
            continue

        name = container.get("name", "")
        readonly = container.get("readonly")
        
        # Determine effective readonly state
        if readonly is None:
            effective_readonly = infer_container_access(name, profile)
        else:
            effective_readonly = readonly

        if effective_readonly:
            readonly_containers.append(name)
        else:
            readwrite_containers.append(name)
            
        # Check for profile mismatches
        if profile and readonly is None:  # Only check inferred permissions
            profile_suggests_readonly = _profile_suggests_readonly(profile)
            container_needs_write = not infer_container_access(name, None)  # Check without profile influence
            
            if profile_suggests_readonly and container_needs_write:
                profile_mismatches.append(name)

    # Mixed access warning
    if readonly_containers and readwrite_containers:
        warnings.append(
            f"⚠️  {dataset_name}: Mixed access - readers: {', '.join(readonly_containers)}, "
            f"writers: {', '.join(readwrite_containers)}\n"
            "   Consider separate datasets or explicit readonly flags"
        )

    # Profile mismatch warnings
    for container_name in profile_mismatches:
        warnings.append(
            f"⚠️  {dataset_name}: Profile mismatch - {container_name} needs write access\n"
            f"   Consider using 'appdata' profile or explicit readonly: false"
        )

    return warnings


def _profile_suggests_readonly(profile: str) -> bool:
    """Check if a profile suggests readonly access by default."""
    readonly_profiles = {"media", "photos", "documents", "backups"}
    return profile.lower() in readonly_profiles


__all__ = [
    "SmartPermissionEvent",
    "apply_smart_defaults",
    "summarize_smart_permission_events",
    "infer_container_access",
    "infer_dataset_permissions",
    "infer_smb_permissions",
    "validate_permissions",
    "detect_permission_issues",
]


def summarize_smart_permission_events(
    events: Sequence[SmartPermissionEvent],
) -> List[str]:
    """Return human-friendly messages for CLI output."""

    summaries: List[str] = []
    for event in events:
        if event.type == "fuzzy-match":
            dataset_label = event.dataset or "(unknown dataset)"
            summaries.append(
                (
                    f"Container '{event.container}' on {dataset_label} "
                    f"matched pattern '{event.pattern}' → inferred {event.access}" 
                    " (override with explicit readonly flag if inaccurate)."
                )
            )
        else:
            dataset_label = event.dataset or "(unknown dataset)"
            summaries.append(
                (
                    f"Container '{event.container}' on {dataset_label} triggered "
                    f"smart-permission event '{event.type}' (access={event.access})."
                )
            )

    return summaries


def detect_permission_issues(
    pools_config: Dict[str, Any],
    *,
    events: Optional[List[SmartPermissionEvent]] = None,
) -> Tuple[List[str], List[str]]:
    """Detect permission issues across all pools and datasets.
    
    Returns:
        Tuple of (warnings, suggestions) for CLI display
    """
    warnings: List[str] = []
    suggestions: List[str] = []
    
    for pool_name, pool_config in pools_config.items():
        if not isinstance(pool_config, dict):
            continue
            
        datasets = pool_config.get("datasets", {})
        for dataset_name, dataset_config in datasets.items():
            if not isinstance(dataset_config, dict):
                continue
                
            full_dataset_name = f"{pool_name}/{dataset_name}"
            
            # Check for missing profiles
            if not dataset_config.get("profile"):
                containers = dataset_config.get("containers", [])
                if containers:
                    warnings.append(
                        f"⚠️  {full_dataset_name}: No profile specified\n"
                        "   Add 'profile: media|appdata|dev|downloads' for smart defaults"
                    )
            
            # Validate permissions for this dataset
            dataset_warnings = validate_permissions(dataset_config, full_dataset_name)
            warnings.extend(dataset_warnings)
            
            # Check for Node.js apps on wrong profiles
            profile = dataset_config.get("profile", "").lower()
            containers = dataset_config.get("containers", [])
            
            for container in containers:
                if not isinstance(container, dict):
                    continue
                    
                name = container.get("name", "").lower()
                readonly = container.get("readonly")
                
                # Detect Node.js/web apps that might need different profiles
                if readonly is None and any(keyword in name for keyword in ["node", "api", "web", "app"]):
                    if profile in ["media", "photos", "backups"]:
                        suggestions.append(
                            f"💡 {full_dataset_name}: '{container.get('name')}' looks like a web app\n"
                            "   Consider 'appdata' profile for readwrite access"
                        )
    
    return warnings, suggestions