"""Static OCI registry/app catalog scaffolding for upcoming Proxmox 9.1 OCI support.

This is intentionally minimal and self-contained so we can start wiring OCI UX
without hitting live registries or adding dependencies.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OciRegistry:
    name: str
    url: str
    note: str = ""


@dataclass
class OciApp:
    name: str
    image: str
    description: str
    registry: str


class OciRegistryCatalog:
    """Static catalog of registries and commonly used images."""

    REGISTRIES: List[OciRegistry] = [
        OciRegistry(name="dockerhub", url="https://registry-1.docker.io", note="Docker Hub"),
        OciRegistry(name="ghcr", url="https://ghcr.io", note="GitHub Container Registry"),
        OciRegistry(name="quay", url="https://quay.io", note="Quay.io"),
    ]

    POPULAR_APPS: List[OciApp] = [
        # Media Servers & Streaming
        OciApp(name="jellyfin", image="jellyfin/jellyfin:latest", description="Media server with transcoding", registry="dockerhub"),
        OciApp(name="plex", image="linuxserver/plex:latest", description="Media server and streaming", registry="dockerhub"),
        OciApp(name="emby", image="linuxserver/emby:latest", description="Media server alternative", registry="dockerhub"),
        OciApp(name="navidrome", image="deluan/navidrome:latest", description="Music server and streamer", registry="dockerhub"),
        
        # Photo Management
        OciApp(name="immich", image="ghcr.io/immich-app/immich-server:latest", description="Self-hosted photo backup", registry="ghcr"),
        OciApp(name="photoprism", image="photoprism/photoprism:latest", description="AI-powered photo management", registry="dockerhub"),
        OciApp(name="photoview", image="viktorstrate/photoview:latest", description="Simple photo gallery", registry="dockerhub"),
        
        # File Storage & Sync
        OciApp(name="nextcloud", image="nextcloud:latest", description="File sync and collaboration", registry="dockerhub"),
        OciApp(name="seafile", image="seafileltd/seafile-mc:latest", description="High-performance file sync", registry="dockerhub"),
        OciApp(name="filebrowser", image="filebrowser/filebrowser:latest", description="Web-based file manager", registry="dockerhub"),
        
        # Home Automation & Smart Home
        OciApp(name="home-assistant", image="ghcr.io/home-assistant/home-assistant:stable", description="Home automation platform", registry="ghcr"),
        OciApp(name="mosquitto", image="eclipse-mosquitto:latest", description="MQTT message broker", registry="dockerhub"),
        OciApp(name="zigbee2mqtt", image="koenkk/zigbee2mqtt:latest", description="Zigbee to MQTT bridge", registry="dockerhub"),
        
        # Document Management & Productivity
        OciApp(name="paperless-ngx", image="ghcr.io/paperless-ngx/paperless-ngx:latest", description="Document management system", registry="ghcr"),
        OciApp(name="calibre-web", image="linuxserver/calibre-web:latest", description="eBook library management", registry="dockerhub"),
        OciApp(name="bookstack", image="linuxserver/bookstack:latest", description="Wiki and documentation", registry="dockerhub"),
        OciApp(name="wikijs", image="ghcr.io/requarks/wiki:latest", description="Modern wiki software", registry="ghcr"),
        
        # Password & Secret Management
        OciApp(name="vaultwarden", image="vaultwarden/server:latest", description="Bitwarden-compatible password manager", registry="dockerhub"),
        OciApp(name="passbolt", image="passbolt/passbolt:latest", description="Team password manager", registry="dockerhub"),
        
        # Monitoring & Management
        OciApp(name="portainer", image="portainer/portainer-ce:latest", description="Container management UI", registry="dockerhub"),
        OciApp(name="uptime-kuma", image="louislam/uptime-kuma:latest", description="Uptime monitoring", registry="dockerhub"),
        OciApp(name="grafana", image="grafana/grafana:latest", description="Metrics visualization", registry="dockerhub"),
        OciApp(name="prometheus", image="prom/prometheus:latest", description="Metrics collection", registry="dockerhub"),
        
        # Network Services
        OciApp(name="pihole", image="pihole/pihole:latest", description="Network-wide ad blocking", registry="dockerhub"),
        OciApp(name="adguardhome", image="adguard/adguardhome:latest", description="Network ad/tracker blocker", registry="dockerhub"),
        OciApp(name="nginx", image="nginx:alpine", description="Web server and reverse proxy", registry="dockerhub"),
        OciApp(name="traefik", image="traefik:latest", description="Modern reverse proxy", registry="dockerhub"),
        
        # Recipe & Cooking
        OciApp(name="tandoor", image="vabene1111/recipes:latest", description="Recipe management", registry="dockerhub"),
        OciApp(name="mealie", image="hkotel/mealie:latest", description="Recipe manager and meal planner", registry="dockerhub"),
        
        # RSS & News
        OciApp(name="freshrss", image="freshrss/freshrss:latest", description="RSS aggregator", registry="dockerhub"),
        OciApp(name="miniflux", image="miniflux/miniflux:latest", description="Minimalist RSS reader", registry="dockerhub"),
    ]

    @classmethod
    def list_registries(cls) -> List[OciRegistry]:
        """List all supported registries."""
        return cls.REGISTRIES

    @classmethod
    def list_popular_apps(cls) -> List[OciApp]:
        """List all apps in the catalog."""
        return cls.POPULAR_APPS

    @classmethod
    def search_apps(cls, query: str) -> List[OciApp]:
        """Search apps by name, image, or description."""
        q = query.lower()
        return [
            app for app in cls.POPULAR_APPS 
            if q in app.name.lower() 
            or q in app.image.lower() 
            or q in app.description.lower()
        ]
    
    @classmethod
    def get_app_by_name(cls, name: str) -> Optional[OciApp]:
        """Get specific app by name."""
        for app in cls.POPULAR_APPS:
            if app.name.lower() == name.lower():
                return app
        return None
    
    @classmethod
    def count_apps(cls) -> int:
        """Get total number of apps in catalog."""
        return len(cls.POPULAR_APPS)
