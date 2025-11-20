"""Integration tests for smart permission defaults via ConfigLoader."""

from pathlib import Path
import textwrap

import pytest

from tengil.config.loader import ConfigLoader


@pytest.fixture()
def temp_config_dir(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


def _write_config(config_dir: Path, text: str) -> Path:
    config_path = config_dir / "tengil.yml"
    config_path.write_text(textwrap.dedent(text).strip())
    return config_path


def _load_config(config_path: Path) -> ConfigLoader:
    loader = ConfigLoader(str(config_path))
    loader.load()
    return loader


def test_loader_applies_appdata_defaults(temp_config_dir: Path):
    config_path = _write_config(
        temp_config_dir,
        """
        pools:
          tank:
            datasets:
              webservices:
                profile: appdata
                containers:
                  - name: my-nodejs-api
                    mount: /app
                shares:
                  smb:
                    name: WebServices
        """,
    )

    loader = _load_config(config_path)
    pools = loader.get_pools()
    dataset = pools["tank"]["datasets"]["webservices"]

    container = dataset["containers"][0]
    smb_share = dataset["shares"]["smb"]

    # Smart permissions now omits readonly when False (default)
    assert "readonly" not in container or container["readonly"] is False
    assert smb_share["writable"] == "yes"
    assert smb_share["read only"] == "no"
    assert loader.get_smart_permission_events() == []


def test_loader_respects_explicit_share_flags(temp_config_dir: Path):
    config_path = _write_config(
        temp_config_dir,
        """
        pools:
          tank:
            datasets:
              webservices:
                profile: appdata
                containers:
                  - name: my-nodejs-api
                    mount: /app
                shares:
                  smb:
                    name: WebServices
                    writable: no
                    read only: yes
        """,
    )

    loader = _load_config(config_path)
    pools = loader.get_pools()
    smb_share = pools["tank"]["datasets"]["webservices"]["shares"]["smb"]

    assert smb_share["writable"] in {False, "no"}
    assert smb_share["read only"] in {True, "yes"}


def test_loader_warns_when_profile_missing(temp_config_dir: Path):
    config_path = _write_config(
        temp_config_dir,
        """
        pools:
          tank:
            datasets:
              logs:
                containers:
                  - name: journald-export
                    mount: /logs
                shares:
                  smb:
                    name: Logs
        """,
    )

    with pytest.warns(UserWarning, match="does not define a profile"):
        loader = _load_config(config_path)

    pools = loader.get_pools()
    dataset = pools["tank"]["datasets"]["logs"]
    container = dataset["containers"][0]
    smb_share = dataset["shares"]["smb"]

    assert container["readonly"] is True
    assert smb_share["writable"] == "no"
    assert smb_share["read only"] == "yes"


def test_loader_records_fuzzy_match_event(temp_config_dir: Path):
    config_path = _write_config(
        temp_config_dir,
        """
        pools:
          tank:
            datasets:
              media:
                profile: media
                containers:
                  - name: jellyfin-nightly
                    mount: /media
        """,
    )

    loader = _load_config(config_path)
    events = loader.get_smart_permission_events()
    assert len(events) == 1
    event = events[0]

    assert event.type == "fuzzy-match"
    assert event.container == "jellyfin-nightly"
    assert event.pattern == "jellyfin"
    assert event.access == "readonly"
    assert event.dataset == "tank/media"
    assert event.exact is False
