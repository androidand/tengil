"""
Integration test: ComposeAnalyzer + OpinionMerger with real romM compose.
"""

import pytest
from pathlib import Path

from tengil.services.docker_compose.analyzer import ComposeAnalyzer
from tengil.services.docker_compose.merger import OpinionMerger


@pytest.fixture
def romm_compose_file():
    """Path to real romM compose file."""
    return "/Users/andreas/dev/tengil/.local/romm-docker-compose.example.yml"


@pytest.fixture
def romm_package():
    """Simplified romM package hints."""
    return {
        'storage_hints': {
            '/path/to/library': {
                'profile': 'media',
                'size_estimate': '500GB',
                'why': 'ROM files range from KB (NES) to GB (Switch). 1M recordsize optimal.',
            },
            '/path/to/assets': {
                'profile': 'media',
                'size_estimate': '50GB',
                'why': 'Save states, screenshots, uploaded artwork.',
            },
            '/path/to/config': {
                'profile': 'dev',
                'size_estimate': '1GB',
                'why': 'romM configuration YAML files.',
            }
        },
        'share_recommendations': {
            '/path/to/library': {
                'smb': True,
                'smb_name': 'ROMs',
                'read_only': False,
                'browseable': True,
                'comment': 'Retro game ROM library'
            }
        },
        'container': {
            'memory': 2048,
            'cores': 2,
            'template': 'debian-12-standard'
        }
    }


def test_analyze_real_romm_compose(romm_compose_file):
    """Test analyzing the real romM compose file."""
    if not Path(romm_compose_file).exists():
        pytest.skip("romM compose file not found")
    
    analyzer = ComposeAnalyzer()
    requirements = analyzer.analyze(romm_compose_file)
    
    # Check services
    assert 'romm' in requirements.services
    assert 'romm-db' in requirements.services
    
    # Check volumes (host mounts only)
    host_paths = requirements.get_host_paths()
    assert '/path/to/library' in host_paths
    assert '/path/to/assets' in host_paths
    assert '/path/to/config' in host_paths
    
    # Check secrets
    assert 'DB_PASSWD' in requirements.secrets
    assert 'ROMM_AUTH_SECRET_KEY' in requirements.secrets
    assert 'MARIADB_ROOT_PASSWORD' in requirements.secrets
    assert 'MARIADB_PASSWORD' in requirements.secrets
    
    # Check ports
    assert '80:8080' in requirements.ports


def test_merge_real_romm_config(romm_compose_file, romm_package):
    """Test full pipeline: analyze romM compose + merge with package."""
    if not Path(romm_compose_file).exists():
        pytest.skip("romM compose file not found")
    
    # Step 1: Analyze compose
    analyzer = ComposeAnalyzer()
    requirements = analyzer.analyze(romm_compose_file)
    
    # Step 2: Merge with Tengil opinions
    merger = OpinionMerger()
    config = merger.merge(requirements, romm_package)
    
    # Verify structure
    assert 'pools' in config
    assert 'tank' in config['pools']
    
    datasets = config['pools']['tank']['datasets']
    
    # Verify datasets created with correct profiles
    assert 'path-to-library' in datasets
    assert 'path-to-assets' in datasets
    assert 'path-to-config' in datasets
    
    # Verify library dataset
    library = datasets['path-to-library']
    assert library['profile'] == 'media'
    assert library['_size_estimate'] == '500GB'
    assert 'ROM files' in library['_why']
    
    # Verify consumers
    consumers = library['consumers']
    assert len(consumers) == 2  # romm container + SMB share
    
    container = next(c for c in consumers if c['type'] == 'container')
    assert container['name'] == 'romm'
    assert container['access'] == 'write'
    assert container['mount'] == '/path/to/library'
    
    smb = next(c for c in consumers if c['type'] == 'smb')
    assert smb['name'] == 'ROMs'
    assert smb['access'] == 'write'
    
    # Verify assets dataset
    assets = datasets['path-to-assets']
    assert assets['profile'] == 'media'
    assert len(assets['consumers']) == 1  # Only romm container
    
    # Verify config dataset
    config_ds = datasets['path-to-config']
    assert config_ds['profile'] == 'dev'
    assert len(config_ds['consumers']) == 1
    
    # Verify container config
    assert 'containers' in config
    assert 'romm' in config['containers']
    assert config['containers']['romm']['memory'] == 2048
    
    # Verify metadata
    assert config['_metadata']['generated_from'] == 'docker_compose'
    assert 'romm' in config['_metadata']['compose_services']
    assert 'romm-db' in config['_metadata']['compose_services']


def test_analyze_to_dict_format(romm_compose_file):
    """Test dictionary output format for CLI/debugging."""
    if not Path(romm_compose_file).exists():
        pytest.skip("romM compose file not found")
    
    analyzer = ComposeAnalyzer()
    result = analyzer.analyze_to_dict(romm_compose_file)
    
    # Verify structure
    assert 'volumes' in result
    assert 'secrets' in result
    assert 'ports' in result
    assert 'services' in result
    assert 'host_paths' in result
    
    # Verify volumes
    assert len(result['volumes']) == 3
    library_vol = next(v for v in result['volumes'] if 'library' in v['host'])
    assert library_vol['container'] == '/romm/library'
    assert library_vol['service'] == 'romm'
    assert not library_vol['readonly']
    
    # Verify secrets are sorted
    assert result['secrets'] == sorted(result['secrets'])
    
    # Verify host paths are sorted
    assert result['host_paths'] == sorted(result['host_paths'])


def test_generated_config_is_valid_tengil_yml(romm_compose_file, romm_package):
    """Test that generated config can be written as valid tengil.yml."""
    if not Path(romm_compose_file).exists():
        pytest.skip("romM compose file not found")
    
    analyzer = ComposeAnalyzer()
    requirements = analyzer.analyze(romm_compose_file)
    
    merger = OpinionMerger()
    config = merger.merge(requirements, romm_package)
    
    # Should be serializable to YAML
    import yaml
    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
    
    # Should be parseable back
    parsed = yaml.safe_load(yaml_str)
    assert 'pools' in parsed
    
    # Verify critical structure
    datasets = parsed['pools']['tank']['datasets']
    assert 'path-to-library' in datasets
    
    library = datasets['path-to-library']
    assert library['profile'] == 'media'
    assert len(library['consumers']) == 2


def test_compare_old_vs_new_package_output(romm_compose_file, romm_package):
    """
    Compare output from old package format vs new compose-based format.
    
    The old rom-manager.yml had ~224 lines with embedded config.
    The new approach generates equivalent config from compose + hints.
    """
    if not Path(romm_compose_file).exists():
        pytest.skip("romM compose file not found")
    
    analyzer = ComposeAnalyzer()
    requirements = analyzer.analyze(romm_compose_file)
    
    merger = OpinionMerger()
    config = merger.merge(requirements, romm_package)
    
    datasets = config['pools']['tank']['datasets']
    
    # OLD approach would have:
    # roms: dataset with manual config
    # assets: dataset with manual config
    # db: dataset with manual config
    
    # NEW approach generates:
    # path-to-library: dataset from compose + hints
    # path-to-assets: dataset from compose + hints
    # path-to-config: dataset from compose + hints
    
    # Key difference: NEW approach uses compose paths as source of truth
    # OLD approach: We maintain paths separately (duplication risk)
    # NEW approach: Compose file defines paths, we add optimization
    
    # Both should have 3 datasets
    assert len(datasets) == 3
    
    # Both should have media profile for ROM storage
    library = datasets['path-to-library']
    assert library['profile'] == 'media'
    
    # Both should have consumers (container + SMB)
    assert len(library['consumers']) == 2
    
    # NEW advantage: Always in sync with compose file!
    # If romM updates compose to add new volume, we automatically pick it up


if __name__ == '__main__':
    # For quick manual testing
    analyzer = ComposeAnalyzer()
    compose_file = "/Users/andreas/dev/tengil/.local/romm-docker-compose.example.yml"
    
    if Path(compose_file).exists():
        print("Analyzing romM compose file...")
        result = analyzer.analyze_to_dict(compose_file)
        
        import json
        print(json.dumps(result, indent=2))
    else:
        print(f"Compose file not found: {compose_file}")
