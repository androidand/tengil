"""
Tests for Docker Compose analyzer.
"""

import pytest
from pathlib import Path

from tengil.services.docker_compose.analyzer import (
    ComposeAnalyzer,
    ComposeRequirements,
    VolumeMount,
)


@pytest.fixture
def analyzer():
    """Create analyzer instance."""
    return ComposeAnalyzer()


@pytest.fixture
def simple_compose(tmp_path):
    """Create a simple compose file."""
    compose = """
version: '3'
services:
  app:
    image: myapp:latest
    volumes:
      - /data:/app/data
      - /config:/app/config:ro
    environment:
      - SECRET_KEY=
      - API_TOKEN=
    ports:
      - "8080:8080"
"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose)
    return str(compose_file)


@pytest.fixture
def multi_service_compose(tmp_path):
    """Create a multi-service compose file (like romM)."""
    compose = """
version: '3'
services:
  romm:
    image: rommapp/romm:latest
    volumes:
      - /path/to/library:/romm/library
      - /path/to/assets:/romm/assets
      - /path/to/config:/romm/config
    environment:
      - DB_HOST=romm-db
      - DB_PASSWD=
      - ROMM_AUTH_SECRET_KEY=
    ports:
      - "80:8080"
    depends_on:
      - romm-db
  
  romm-db:
    image: mariadb:latest
    environment:
      - MARIADB_ROOT_PASSWORD=
      - MARIADB_DATABASE=romm
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose)
    return str(compose_file)


@pytest.fixture
def compose_with_long_format(tmp_path):
    """Create compose with long-format volume syntax."""
    compose = """
version: '3'
services:
  app:
    image: myapp:latest
    volumes:
      - type: bind
        source: /data
        target: /app/data
      - type: bind
        source: /readonly
        target: /app/readonly
        read_only: true
      - type: volume
        source: named_volume
        target: /app/volume
"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose)
    return str(compose_file)


def test_parse_simple_compose(analyzer, simple_compose):
    """Test parsing a simple compose file."""
    requirements = analyzer.analyze(simple_compose)
    
    # Check services
    assert len(requirements.services) == 1
    assert 'app' in requirements.services
    
    # Check volumes
    assert len(requirements.volumes) == 2
    
    data_vol = next(v for v in requirements.volumes if v.host == '/data')
    assert data_vol.container == '/app/data'
    assert data_vol.service == 'app'
    assert not data_vol.readonly
    
    config_vol = next(v for v in requirements.volumes if v.host == '/config')
    assert config_vol.container == '/app/config'
    assert config_vol.readonly
    
    # Check secrets
    assert len(requirements.secrets) == 2
    assert 'SECRET_KEY' in requirements.secrets
    assert 'API_TOKEN' in requirements.secrets
    
    # Check ports
    assert len(requirements.ports) == 1
    assert '8080:8080' in requirements.ports


def test_parse_multi_service_compose(analyzer, multi_service_compose):
    """Test parsing compose with multiple services."""
    requirements = analyzer.analyze(multi_service_compose)
    
    # Check services
    assert len(requirements.services) == 2
    assert 'romm' in requirements.services
    assert 'romm-db' in requirements.services
    
    # Check volumes (only host mounts, not named volumes)
    assert len(requirements.volumes) == 3
    
    library_vol = next(v for v in requirements.volumes if 'library' in v.host)
    assert library_vol.container == '/romm/library'
    assert library_vol.service == 'romm'
    
    # Check secrets
    assert 'DB_PASSWD' in requirements.secrets
    assert 'ROMM_AUTH_SECRET_KEY' in requirements.secrets
    assert 'MARIADB_ROOT_PASSWORD' in requirements.secrets
    
    # DB_HOST should NOT be a secret (has value)
    assert 'DB_HOST' not in requirements.secrets
    assert 'MARIADB_DATABASE' not in requirements.secrets


def test_parse_long_format_volumes(analyzer, compose_with_long_format):
    """Test parsing long-format volume syntax."""
    requirements = analyzer.analyze(compose_with_long_format)
    
    # Should have 2 bind mounts (not the named volume)
    assert len(requirements.volumes) == 2
    
    data_vol = next(v for v in requirements.volumes if v.host == '/data')
    assert data_vol.container == '/app/data'
    assert not data_vol.readonly
    
    readonly_vol = next(v for v in requirements.volumes if v.host == '/readonly')
    assert readonly_vol.container == '/app/readonly'
    assert readonly_vol.readonly


def test_get_host_paths(analyzer, simple_compose):
    """Test extracting unique host paths."""
    requirements = analyzer.analyze(simple_compose)
    
    host_paths = requirements.get_host_paths()
    assert len(host_paths) == 2
    assert '/data' in host_paths
    assert '/config' in host_paths


def test_analyze_to_dict(analyzer, simple_compose):
    """Test dictionary output format."""
    result = analyzer.analyze_to_dict(simple_compose)
    
    assert 'volumes' in result
    assert 'secrets' in result
    assert 'ports' in result
    assert 'services' in result
    assert 'host_paths' in result
    
    assert len(result['volumes']) == 2
    assert len(result['secrets']) == 2
    assert len(result['services']) == 1
    assert len(result['host_paths']) == 2


def test_environment_dict_format(analyzer, tmp_path):
    """Test parsing environment as dictionary."""
    compose = """
version: '3'
services:
  app:
    image: myapp:latest
    environment:
      FILLED_VAR: "has_value"
      EMPTY_VAR: ""
      NULL_VAR: null
"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose)
    
    requirements = analyzer.analyze(str(compose_file))
    
    # Only empty/null vars are secrets
    assert 'EMPTY_VAR' in requirements.secrets or 'NULL_VAR' in requirements.secrets
    assert 'FILLED_VAR' not in requirements.secrets


def test_ignore_named_volumes(analyzer, tmp_path):
    """Test that named volumes are ignored."""
    compose = """
version: '3'
services:
  app:
    image: myapp:latest
    volumes:
      - named_volume:/app/data
      - /host/path:/app/config

volumes:
  named_volume:
"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose)
    
    requirements = analyzer.analyze(str(compose_file))
    
    # Should only have host mount
    assert len(requirements.volumes) == 1
    assert requirements.volumes[0].host == '/host/path'


def test_invalid_compose(analyzer, tmp_path):
    """Test handling invalid compose file."""
    compose_file = tmp_path / "invalid.yml"
    compose_file.write_text("not valid yaml: [")
    
    with pytest.raises(Exception):
        analyzer.analyze(str(compose_file))


def test_missing_services_section(analyzer, tmp_path):
    """Test handling compose without services."""
    compose = """
version: '3'
volumes:
  data:
"""
    compose_file = tmp_path / "docker-compose.yml"
    compose_file.write_text(compose)
    
    with pytest.raises(ValueError, match="no services section"):
        analyzer.analyze(str(compose_file))


def test_volume_mount_equality():
    """Test VolumeMount equality and hashing."""
    vol1 = VolumeMount(host='/data', container='/app/data', service='app')
    vol2 = VolumeMount(host='/data', container='/app/data', service='app')
    vol3 = VolumeMount(host='/other', container='/app/data', service='app')
    
    assert vol1 == vol2
    assert vol1 != vol3
    assert hash(vol1) == hash(vol2)
    assert hash(vol1) != hash(vol3)


def test_compose_requirements_deduplication():
    """Test that duplicate volumes are not added."""
    requirements = ComposeRequirements()
    
    requirements.add_volume('/data', '/app/data', 'app')
    requirements.add_volume('/data', '/app/data', 'app')  # Duplicate
    
    assert len(requirements.volumes) == 1


def test_secrets_are_unique():
    """Test that secrets are deduplicated."""
    requirements = ComposeRequirements()
    
    requirements.add_secret('SECRET_KEY')
    requirements.add_secret('SECRET_KEY')  # Duplicate
    requirements.add_secret('API_TOKEN')
    
    assert len(requirements.secrets) == 2


def test_read_nonexistent_file(analyzer):
    """Test error handling for nonexistent file."""
    with pytest.raises(ValueError, match="Failed to read"):
        analyzer.analyze('/nonexistent/file.yml')


# URL download tests would require mocking or live tests
# Skipping for now, but structure is in place
@pytest.mark.skip(reason="Requires network or mocking")
def test_download_from_url(analyzer):
    """Test downloading compose from URL."""
    url = "https://raw.githubusercontent.com/rommapp/romm/master/docker-compose.example.yml"
    requirements = analyzer.analyze(url)
    
    assert len(requirements.services) > 0
    assert len(requirements.volumes) > 0
