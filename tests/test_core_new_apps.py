"""Tests for OCI/LXC app parsing in the new core draft."""
from tengil.core_new import Config, OciAppSpec


def test_apps_parse_dict():
    data = {
        "apps": [
            {
                "name": "jellyfin",
                "image": "jellyfin/jellyfin:latest",
                "runtime": "oci",
                "dataset": "media",
                "mount": "/media",
                "env": {"JELLYFIN_PublishedServerUrl": "http://jellyfin.local:8096"},
                "ports": [8096, 8920],
                "volumes": [{"name": "config", "path": "/config"}],
            }
        ]
    }

    apps = Config(data).apps
    assert len(apps) == 1
    spec = apps[0]
    assert isinstance(spec, OciAppSpec)
    assert spec.name == "jellyfin"
    assert spec.image == "jellyfin/jellyfin:latest"
    assert spec.runtime == "oci"
    assert spec.dataset == "media"
    assert spec.mount == "/media"
    assert spec.env["JELLYFIN_PublishedServerUrl"] == "http://jellyfin.local:8096"
    assert 8096 in spec.ports
    assert spec.volumes[0]["path"] == "/config"


def test_apps_parse_string_defaults():
    data = {"apps": ["ghcr.io/home-assistant/home-assistant:stable"]}
    apps = Config(data).apps
    assert len(apps) == 1
    spec = apps[0]
    assert spec.name == "home-assistant"
    assert spec.image == "ghcr.io/home-assistant/home-assistant:stable"
    assert spec.runtime == "oci"
    assert spec.dataset == "appdata"
    assert spec.mount == "/data"
    assert spec.env == {}
    assert spec.ports == []
    assert spec.volumes == []
