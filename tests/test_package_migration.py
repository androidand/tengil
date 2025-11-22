"""Tests for modernized packages using docker_compose integration."""
from pathlib import Path

import pytest

from tengil.core.package_loader import PackageLoader


class TestAIWorkstationPackage:
    """Test modernized ai-workstation.yml with docker_compose integration."""
    
    @pytest.fixture
    def package_loader(self):
        """Create package loader."""
        return PackageLoader()
    
    @pytest.fixture
    def ai_workstation(self, package_loader):
        """Load ai-workstation.yml package."""
        return package_loader.load_package("ai-workstation")
    
    def test_package_metadata(self, ai_workstation):
        """Test package metadata is preserved."""
        pkg = ai_workstation

        assert pkg.name == "AI Workstation"
        assert pkg.category == "Development"
        assert "ai" in pkg.tags
        assert "llm" in pkg.tags
        assert "ollama" in pkg.tags

        # Requirements preserved
        assert pkg.requirements.min_ram_mb == 16384
        assert pkg.requirements.recommended_cores >= 4        # Components preserved
        assert len(pkg.components) == 5
        assert "Ollama" in pkg.components[0]
    
    def test_docker_compose_section(self, ai_workstation):
        """Test docker_compose section structure."""
        pkg = ai_workstation

        assert pkg.docker_compose is not None

        # Check main service (simplified format)
        assert 'cache' in pkg.docker_compose
        assert pkg.docker_compose['cache'] == 'compose_cache/ollama/docker-compose.yml'
        assert 'image' in pkg.docker_compose
        assert 'ollama/ollama' in pkg.docker_compose['image']

        # Optional services
        assert 'optional_services' in pkg.docker_compose
        optional = pkg.docker_compose['optional_services']
        assert len(optional) >= 1
        assert optional[0]['key'] == 'include_jupyter'
        assert 'cache' in optional[0] or 'image' in optional[0]
    
    def test_storage_hints(self, ai_workstation):
        """Test storage_hints for optimization."""
        pkg = ai_workstation

        assert pkg.storage_hints is not None

        # Model storage
        models = pkg.storage_hints['/root/.ollama']
        assert models['profile'] == 'dev'
        assert models['size_estimate'] == '200GB'
        assert models['mount_as'] == '/models'
        assert 'why' in models

        # Jupyter notebooks (uses /notebooks mount point, not /home/jovyan/work)
        notebooks = pkg.storage_hints['/notebooks']
        assert notebooks['profile'] == 'dev'
        assert notebooks['size_estimate'] == '50GB'
        assert notebooks['mount_as'] == '/notebooks'

        # Output images
        outputs = pkg.storage_hints['/outputs']
        assert outputs['profile'] == 'media'
        assert outputs['size_estimate'] == '100GB'
    
    def test_share_recommendations(self, ai_workstation):
        """Test SMB share recommendations."""
        pkg = ai_workstation
        
        assert pkg.share_recommendations is not None
        
        # Models share
        models = pkg.share_recommendations['/root/.ollama']
        assert models['smb'] is True
        assert models['smb_name'] == 'AI-Models'
        assert models['read_only'] is False
        assert models['browseable'] is True
        
        # Images share (read-only)
        outputs = pkg.share_recommendations['/outputs']
        assert outputs['smb'] is True
        assert outputs['read_only'] is True
    
    def test_container_config(self, ai_workstation):
        """Test container resource configuration."""
        pkg = ai_workstation
        
        assert pkg.container is not None
        assert pkg.container['template'] == 'debian-12-standard'
        assert pkg.container['disk_size'] == 100
        assert 'tteck/docker' in pkg.container['post_install']
        assert 'tteck/portainer' in pkg.container['post_install']
    
    def test_deployment_config(self, ai_workstation):
        """Test deployment configuration."""
        pkg = ai_workstation
        
        # Deployment is not yet part of Package dataclass
        # But it exists in YAML for future use
        # For now, just verify container config has what we need
        assert pkg.container is not None
        assert 'memory' in pkg.container or 'template' in pkg.container
    
    def test_customize_section(self, ai_workstation):
        """Test interactive customize prompts."""
        pkg = ai_workstation
        
        # Customize section parsed into prompts
        assert len(pkg.prompts) == 4
        
        # Check prompt IDs exist
        prompt_ids = [p.id for p in pkg.prompts]
        assert 'pool_name' in prompt_ids
        assert 'ollama_memory' in prompt_ids
        assert 'ollama_cores' in prompt_ids
        assert 'include_jupyter' in prompt_ids
        
        # Check memory prompt has validation
        mem_prompt = next(p for p in pkg.prompts if p.id == 'ollama_memory')
        assert mem_prompt.type == 'int'
        assert mem_prompt.min == 8192
        assert mem_prompt.max == 32768


class TestNASCompletePackage:
    """Test modernized nas-complete.yml with docker_compose integration."""
    
    @pytest.fixture
    def package_loader(self):
        """Create package loader."""
        return PackageLoader()
    
    @pytest.fixture
    def nas_complete(self, package_loader):
        """Load nas-complete.yml package."""
        return package_loader.load_package("nas-complete")
    
    def test_package_metadata(self, nas_complete):
        """Test package metadata is preserved."""
        pkg = nas_complete

        assert pkg.name == "NAS Complete"
        assert pkg.category == "Complete"
        assert "nas" in pkg.tags
        assert "complete" in pkg.tags
        assert "jellyfin" in pkg.tags

        # Requirements preserved
        assert pkg.requirements.min_ram_mb == 16384
        assert pkg.requirements.min_disk_gb == 200
        assert pkg.requirements.recommended_ram_mb == 32768
        
        # Components preserved
        assert len(pkg.components) == 7
        assert "File sharing" in pkg.components[0]
    
    def test_docker_compose_section(self, nas_complete):
        """Test docker_compose section with multiple sources."""
        pkg = nas_complete
        
        assert pkg.docker_compose is not None
        
        # Should have sources array
        sources = pkg.docker_compose.get('sources', [])
        assert len(sources) == 2
        
        # Check jellyfin source
        jellyfin = sources[0]
        assert jellyfin['name'] == 'jellyfin'
        assert 'source' in jellyfin
        assert '/movies' in jellyfin['managed_volumes']
        assert '/tvshows' in jellyfin['managed_volumes']
        
        # Check arr-stack source
        arr_stack = sources[1]
        assert arr_stack['name'] == 'arr-stack'
        assert '/downloads' in arr_stack['managed_volumes']
        
        # Check optional services
        optional = pkg.docker_compose.get('optional_services', [])
        assert len(optional) == 3
        
        optional_keys = [svc['key'] for svc in optional]
        assert 'include_immich' in optional_keys
        assert 'include_nextcloud' in optional_keys
        assert 'include_pihole' in optional_keys
    
    def test_storage_hints(self, nas_complete):
        """Test storage_hints for all paths."""
        pkg = nas_complete
        
        assert pkg.storage_hints is not None
        assert len(pkg.storage_hints) == 7
        
        # Media paths
        assert '/movies' in pkg.storage_hints
        assert pkg.storage_hints['/movies']['profile'] == 'media'
        assert '2TB' in pkg.storage_hints['/movies']['size_estimate']
        
        assert '/tvshows' in pkg.storage_hints
        assert pkg.storage_hints['/tvshows']['profile'] == 'media'
        
        # Downloads (critical for hardlinks)
        assert '/downloads' in pkg.storage_hints
        assert pkg.storage_hints['/downloads']['profile'] == 'downloads'
        assert 'critical_note' in pkg.storage_hints['/downloads']
        assert 'same pool' in pkg.storage_hints['/downloads']['critical_note']
        
        # Optional service paths
        assert '/photos' in pkg.storage_hints
        assert '/documents' in pkg.storage_hints
        assert '/config' in pkg.storage_hints
        
        # General storage
        assert '/files' in pkg.storage_hints
    
    def test_share_recommendations(self, nas_complete):
        """Test SMB share recommendations."""
        pkg = nas_complete
        
        assert pkg.share_recommendations is not None
        assert len(pkg.share_recommendations) == 6
        
        # Movies share
        movies = pkg.share_recommendations['/movies']
        assert movies['smb'] is True
        assert movies['smb_name'] == 'Movies'
        assert movies['browseable'] is True
        
        # Downloads share
        downloads = pkg.share_recommendations['/downloads']
        assert downloads['smb'] is True
        assert downloads['smb_name'] == 'Downloads'
        
        # Photos, Documents, Files, Config
        assert '/photos' in pkg.share_recommendations
        assert '/documents' in pkg.share_recommendations
        assert '/files' in pkg.share_recommendations
    
    def test_container_config(self, nas_complete):
        """Test container resource configuration."""
        pkg = nas_complete
        
        assert pkg.container is not None
        assert pkg.container['memory'] == 16384  # 16GB for full stack
        assert pkg.container['cores'] == 8
        assert 'tteck/docker' in pkg.container['post_install']
        assert 'tteck/portainer' in pkg.container['post_install']
    
    def test_customize_prompts(self, nas_complete):
        """Test interactive customize prompts."""
        pkg = nas_complete
        
        # Should have 4 prompts (pool + 3 optional services)
        assert len(pkg.prompts) == 4
        
        # Check prompt IDs exist
        prompt_ids = [p.id for p in pkg.prompts]
        assert 'pool_name' in prompt_ids
        assert 'include_immich' in prompt_ids
        assert 'include_nextcloud' in prompt_ids
        assert 'include_pihole' in prompt_ids
        
        # Check bool prompts
        immich_prompt = next(p for p in pkg.prompts if p.id == 'include_immich')
        assert immich_prompt.type == 'bool'
        assert immich_prompt.default is True


class TestRomManagerCompose:
    """Test rom-manager-compose.yml as reference example."""
    
    @pytest.fixture
    def package_loader(self):
        return PackageLoader()
    
    def test_rom_manager_compose_structure(self, package_loader):
        """Verify rom-manager-compose has correct structure."""
        pkg = package_loader.load_package("rom-manager-compose")
        
        # Has docker_compose section
        assert pkg.docker_compose is not None
        assert 'cache' in pkg.docker_compose or 'source' in pkg.docker_compose
        
        # Has storage_hints
        assert pkg.storage_hints is not None
        assert len(pkg.storage_hints) >= 2
        
        # Has share_recommendations
        assert pkg.share_recommendations is not None


class TestPackageValidation:
    """Test package validation and error handling."""
    
    @pytest.fixture
    def package_loader(self):
        return PackageLoader()
    
    def test_invalid_docker_compose_source(self, package_loader, tmp_path):
        """Test error handling for invalid compose source."""
        bad_package = tmp_path / "bad-package.yml"
        bad_package.write_text("""
name: Bad Package
description: Invalid compose source
category: Test

docker_compose:
  source: "https://invalid.url.that.does.not.exist/compose.yml"

storage_hints:
  "/data":
    profile: dev
    size_estimate: "10GB"
""")
        
        pkg = package_loader.load_package_file(bad_package)
        assert pkg.docker_compose is not None
        
        # Rendering will fail when it tries to download
        with pytest.raises((ValueError, Exception)):
            user_inputs = {}
            package_loader.render_compose_config(pkg, user_inputs)
    
    def test_missing_storage_hints(self, package_loader, tmp_path):
        """Test package with compose but no storage hints."""
        no_hints = tmp_path / "no-hints.yml"
        no_hints.write_text("""
name: No Hints Package
description: Compose without storage hints
category: Test

docker_compose:
  sources:
    - name: test
      source: "https://example.com/compose.yml"
      managed_volumes:
        - /data
""")
        
        pkg = package_loader.load_package_file(no_hints)
        
        # Should load but storage_hints will be None or empty
        assert pkg.docker_compose is not None
        # Merger will use defaults for volumes without hints


def test_all_packages_are_valid():
    """Smoke test: ensure all package files are valid YAML."""
    pkg_dir = Path(__file__).parent.parent / "tengil" / "packages"
    loader = PackageLoader()
    
    for pkg_file in pkg_dir.glob("*.yml"):
        if pkg_file.name in ['__init__.py', 'README.md', 'APP_GUIDE.md']:
            continue
        
        try:
            pkg = loader.load_package(pkg_file.stem)
            assert pkg.name is not None
            assert pkg.category is not None
            print(f"✓ {pkg_file.name}: {pkg.name}")
        except Exception as e:
            pytest.fail(f"Failed to load {pkg_file.name}: {e}")

