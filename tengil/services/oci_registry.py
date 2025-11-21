"""Static OCI registry/app catalog scaffolding for upcoming Proxmox 9.1 OCI support.

This is intentionally minimal and self-contained so we can start wiring OCI UX
without hitting live registries or adding dependencies.
"""
from dataclasses import dataclass
from typing import List


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
        OciApp(name="portainer", image="portainer/portainer-ce:latest", description="Docker management UI", registry="dockerhub"),
        OciApp(name="jellyfin", image="jellyfin/jellyfin:latest", description="Media server", registry="dockerhub"),
        OciApp(name="immich", image="ghcr.io/immich-app/immich-server:latest", description="Self-hosted photos", registry="ghcr"),
        OciApp(name="home-assistant", image="ghcr.io/home-assistant/home-assistant:stable", description="Home automation", registry="ghcr"),
        OciApp(name="nextcloud", image="nextcloud:latest", description="File sync and share", registry="dockerhub"),
        OciApp(name="pihole", image="pihole/pihole:latest", description="Network-wide ad blocking", registry="dockerhub"),
    ]

    @classmethod
    def list_registries(cls) -> List[OciRegistry]:
        return cls.REGISTRIES

    @classmethod
    def list_popular_apps(cls) -> List[OciApp]:
        return cls.POPULAR_APPS

    @classmethod
    def search_apps(cls, query: str) -> List[OciApp]:
        q = query.lower()
        return [app for app in cls.POPULAR_APPS if q in app.name.lower() or q in app.image.lower()]
