"""Tests for static OCI catalog helpers."""
from tengil.services.oci_registry import OciRegistryCatalog, OciApp


def test_list_registries():
    registries = OciRegistryCatalog.list_registries()
    assert any(reg.name == "dockerhub" for reg in registries)
    assert any(reg.name == "ghcr" for reg in registries)


def test_popular_apps_contains_known_images():
    apps = OciRegistryCatalog.list_popular_apps()
    images = {app.image for app in apps}
    assert "portainer/portainer-ce:latest" in images
    assert any(app.name == "home-assistant" for app in apps)


def test_search_apps_matches_name_and_image():
    results = OciRegistryCatalog.search_apps("jellyfin")
    assert results, "Expected at least one match for jellyfin"
    assert all(isinstance(app, OciApp) for app in results)

    # Image substring should match too
    assert OciRegistryCatalog.search_apps("immich-app")
