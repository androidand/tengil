"""Tests for desired-state serialization."""
import yaml

from tengil.config.loader import ConfigLoader


def test_build_desired_state_from_config(tmp_path):
    config = {
        "pools": {
            "tank": {
                "datasets": {
                    "media/movies": {
                        "profile": "media",
                        "mountpoint": "/tank/media/movies",
                        "shares": {"smb": {"name": "movies"}},
                        "containers": [
                            {"name": "jellyfin", "mount": "/media/movies", "permissions": ["read"]},
                            {"name": "immich", "mount": "/mnt/library", "permissions": ["read", "write"]},
                        ],
                        "zfs": {"recordsize": "1M"},
                    },
                    "backups": {
                        "profile": "backups",
                        "containers": [{"name": "restic", "mount": "/data"}],
                        "zfs": {"compression": "zstd"},
                    },
                }
            }
        }
    }

    config_path = tmp_path / "tengil.yml"
    config_path.write_text(yaml.safe_dump(config))

    loader = ConfigLoader(str(config_path))
    loader.load()

    desired = loader.build_desired_state()

    assert desired["metadata"]["source"] == str(config_path)
    assert desired["metadata"]["dataset_count"] == 3
    assert "tank/media/movies" in desired["datasets"]

    movies = desired["datasets"]["tank/media/movies"]
    assert movies["profile"] == "media"
    assert movies["mountpoint"] == "/tank/media/movies"
    assert movies["shares"]["smb"]["name"] == "movies"
    assert len(movies["containers"]) == 2

    container_summary = desired["containers"]["jellyfin"]
    assert container_summary["mounts"][0]["dataset"] == "tank/media/movies"
    assert "media" in container_summary["profiles"]
