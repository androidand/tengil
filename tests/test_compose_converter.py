"""Tests for Docker Compose to Tengil config converter."""
import tempfile
from pathlib import Path

import pytest
import yaml

from tengil.services.compose_converter import ComposeConverter, DatasetSpec
from tengil.services.docker_compose.analyzer import ComposeRequirements, VolumeMount


@pytest.fixture
def converter():
    """Create a ComposeConverter instance."""
    return ComposeConverter()


def test_simple_compose_conversion(converter, tmp_path):
    """Convert a simple single-service compose file."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example/app
    volumes:
      - /photos:/app/photos
      - /config:/app/config
    ports:
      - "8080:8080"
    environment:
      - DB_PASSWORD=
""")

    result = converter.convert(str(compose), app_name="test-app")

    assert result.app_name == "test-app"
    assert result.pool == "tank"
    assert len(result.datasets) == 2
    assert result.container_memory == 2048  # Default
    assert result.container_cores == 2
    assert "DB_PASSWORD" in result.secrets_needed
    assert "8080:8080" in result.ports


def test_media_app_classification(converter, tmp_path):
    """Media apps get higher resource allocation."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  jellyfin:
    image: jellyfin/jellyfin
    volumes:
      - /media:/media
""")

    result = converter.convert(str(compose))

    # Media apps should get more resources
    assert result.container_memory == 4096  # Media default
    assert result.container_cores == 2


def test_dataset_profile_classification(converter):
    """Test path classification for dataset profiles."""
    # Media paths
    profile, _ = converter._classify_path("/photos")
    assert profile == "media"

    profile, _ = converter._classify_path("/media/movies")
    assert profile == "media"

    # Database paths
    profile, _ = converter._classify_path("/var/lib/postgresql")
    assert profile == "database"

    profile, _ = converter._classify_path("/db/data")
    assert profile == "database"

    # Downloads
    profile, _ = converter._classify_path("/downloads")
    assert profile == "downloads"

    # Appdata (default)
    profile, _ = converter._classify_path("/config")
    assert profile == "appdata"

    profile, _ = converter._classify_path("/app/data")
    assert profile == "appdata"


def test_dataset_naming(converter):
    """Test dataset name generation from paths."""
    purpose = converter._extract_purpose("/app/photos")
    assert purpose == "photos"

    purpose = converter._extract_purpose("/config")
    assert purpose == "config"

    purpose = converter._extract_purpose("/var/lib/postgresql/data")
    assert purpose == "data"


def test_size_estimation(converter):
    """Test storage size estimation."""
    # Media photos should be large
    size = converter._estimate_size("media", "/photos")
    assert size == "2T"

    # Database should be medium
    size = converter._estimate_size("database", "/postgres/data")
    assert size == "100G"

    # Config should be small
    size = converter._estimate_size("appdata", "/config")
    assert size == "10G"


def test_multi_service_compose(converter, tmp_path):
    """Multi-service compose files should trigger warning."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example/app
    volumes:
      - /data:/data
  db:
    image: postgres
  redis:
    image: redis
""")

    result = converter.convert(str(compose))

    assert len(result.services) == 3
    assert any("Multi-service" in w for w in result.warnings)


def test_compose_with_no_volumes(converter, tmp_path):
    """Compose with no host mounts should warn."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example/app
    ports:
      - "8080:8080"
""")

    result = converter.convert(str(compose))

    assert len(result.datasets) == 0
    assert any("No host volume mounts" in w for w in result.warnings)


def test_yaml_generation(converter, tmp_path):
    """Test YAML config generation."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  immich:
    image: immich/server
    volumes:
      - /photos:/usr/src/app/upload
      - /config:/config
    environment:
      - DB_PASSWORD=
      - REDIS_PASSWORD=
    ports:
      - "2283:3001"
""")

    result = converter.convert(str(compose), app_name="immich")
    yaml_config = converter.to_yaml(result)

    # Verify YAML is valid
    parsed = yaml.safe_load(yaml_config)
    assert "pools" in parsed
    assert "tank" in parsed["pools"]
    assert "datasets" in parsed["pools"]["tank"]
    assert "containers" in parsed

    # Check container config
    assert "immich" in parsed["containers"]
    container = parsed["containers"]["immich"]
    assert container["auto_create"] is True
    assert container["privileged"] is True
    assert container["requires_docker"] is True
    assert "docker_compose" in container

    # Verify comments are present in raw YAML
    assert "# Tengil configuration" in yaml_config
    assert "# Generated from:" in yaml_config


def test_app_name_auto_detection(converter, tmp_path):
    """App name should be auto-detected from compose path or services."""
    # From parent directory
    app_dir = tmp_path / "jellyfin"
    app_dir.mkdir()
    compose = app_dir / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example
""")

    result = converter.convert(str(compose))
    assert result.app_name == "jellyfin"

    # From service name when parent is generic
    compose2 = tmp_path / "docker-compose.yml"
    compose2.write_text("""
version: '3'
services:
  immich:
    image: immich/server
""")

    result2 = converter.convert(str(compose2))
    assert result2.app_name == "immich"


def test_name_sanitization(converter):
    """Test name sanitization for ZFS/container names."""
    # Uppercase to lowercase
    assert converter._sanitize_name("MyApp") == "myapp"

    # Spaces to dashes
    assert converter._sanitize_name("my app") == "my-app"

    # Special chars removed
    assert converter._sanitize_name("app@v1.0") == "app-v1-0"

    # Collapse multiple dashes
    assert converter._sanitize_name("my--app__v1") == "my-app-v1"

    # Strip leading/trailing dashes
    assert converter._sanitize_name("-app-") == "app"


def test_readonly_volume_mapping(converter, tmp_path):
    """Readonly volumes should be marked readonly in datasets."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example
    volumes:
      - /media:/media:ro
      - /config:/config
""")

    result = converter.convert(str(compose))

    # Find media dataset (readonly)
    media_ds = next(ds for ds in result.datasets if "/media" in ds.mount_point)
    assert media_ds.readonly is True

    # Config should be read-write
    config_ds = next(ds for ds in result.datasets if "/config" in ds.mount_point)
    assert config_ds.readonly is False


def test_dataset_size_estimates(converter, tmp_path):
    """Test that different dataset types get appropriate size estimates."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example
    volumes:
      - /photos:/photos
      - /config:/config
      - /db:/var/lib/postgresql
      - /downloads:/downloads
""")

    result = converter.convert(str(compose))

    # Media (photos) should be large
    photos_ds = next(ds for ds in result.datasets if "photos" in ds.name)
    assert photos_ds.size_estimate == "2T"

    # Config should be small
    config_ds = next(ds for ds in result.datasets if "config" in ds.name)
    assert config_ds.size_estimate == "10G"

    # Database should be medium
    db_ds = next(ds for ds in result.datasets if ds.profile == "database")
    assert db_ds.size_estimate == "100G"

    # Downloads should be large
    downloads_ds = next(ds for ds in result.datasets if "downloads" in ds.name)
    assert downloads_ds.size_estimate == "500G"


def test_secrets_detection(converter, tmp_path):
    """Test detection of secrets from environment variables."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example
    environment:
      DB_HOST: postgres
      DB_PASSWORD:
      REDIS_PASSWORD:
      API_KEY:
""")

    result = converter.convert(str(compose))

    assert "DB_PASSWORD" in result.secrets_needed
    assert "REDIS_PASSWORD" in result.secrets_needed
    assert "API_KEY" in result.secrets_needed
    assert "DB_HOST" not in result.secrets_needed  # Has value


def test_pool_override(converter, tmp_path):
    """Test custom pool selection."""
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""
version: '3'
services:
  app:
    image: example
    volumes:
      - /data:/data
""")

    result = converter.convert(str(compose), pool="storage")

    assert result.pool == "storage"

    # Verify YAML has correct pool
    yaml_config = converter.to_yaml(result)
    parsed = yaml.safe_load(yaml_config)
    assert "storage" in parsed["pools"]
