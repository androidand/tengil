"""Tests for parsing app repository specs from Tengil config."""

import textwrap
from pathlib import Path

import pytest

from tengil.config.loader import ConfigLoader


@pytest.fixture()
def temp_config_dir(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


def test_config_loader_parses_inline_app_repo(temp_config_dir: Path):
    config_path = temp_config_dir / "tengil.yml"
    config_path.write_text(
        textwrap.dedent(
            """
            pools:
              tank:
                type: zfs
                datasets: {}
            apps:
              repos:
                - name: media-config
                  target: jellyfin
                  repo: https://example.com/media-config.git
                  branch: develop
                  path: /srv/apps/media-config
                  manifests:
                    glob: "*.app.yml"
                    depth: 2
            """
        ).strip()
    )

    loader = ConfigLoader(str(config_path))
    loader.load()
    repos = loader.get_app_repos()

    assert len(repos) == 1
    spec = repos[0]
    assert spec.name == "media-config"
    assert spec.target == "jellyfin"
    assert spec.repo == "https://example.com/media-config.git"
    assert spec.branch == "develop"
    assert spec.path == "/srv/apps/media-config"
    assert spec.manifest_glob == "*.app.yml"
    assert spec.manifest_depth == 2


def test_config_loader_supports_spec_reference(temp_config_dir: Path):
    spec_file = temp_config_dir / "app-repos.yml"
    spec_file.write_text(
        textwrap.dedent(
            """
            repos:
              - name: jellyfin-config
                target: jellyfin
                repo: https://example.com/jellyfin-config.git
                path: /srv/apps/jellyfin-config
            """
        ).strip()
    )

    config_path = temp_config_dir / "tengil.yml"
    config_path.write_text(
        textwrap.dedent(
            """
            pools:
              tank:
                type: zfs
                datasets: {}
            apps:
              repos:
                - alias: jellyfin
                  spec: app-repos.yml
                  select: jellyfin-config
                  branch: feature/preview
            """
        ).strip()
    )

    loader = ConfigLoader(str(config_path))
    loader.load()
    repos = loader.get_app_repos()

    assert len(repos) == 1
    spec = repos[0]
    assert spec.name == "jellyfin"
    assert spec.target == "jellyfin"
    assert spec.repo == "https://example.com/jellyfin-config.git"
    assert spec.path == "/srv/apps/jellyfin-config"
    assert spec.branch == "feature/preview"
