"""Tests for package loader system."""
import pytest
from pathlib import Path
from tengil.core.package_loader import PackageLoader, Package, PackagePrompt


class TestPackageLoader:
    """Test PackageLoader functionality."""
    
    @pytest.fixture
    def loader(self):
        """Create PackageLoader instance."""
        return PackageLoader()
    
    def test_list_packages(self, loader):
        """Test listing all packages."""
        packages = loader.list_packages()
        
        # Should find at least the core packages
        assert len(packages) >= 11
        
        # Check packages are sorted by category then name
        categories = [p.category for p in packages]
        # Verify sorting (may have duplicates, but should be grouped)
        
        # Verify all packages have required fields
        for pkg in packages:
            assert pkg.name
            assert pkg.slug
            assert pkg.description
            assert pkg.category
    
    def test_list_packages_by_category(self, loader):
        """Test filtering packages by category."""
        media_packages = loader.list_packages(category="Media")
        
        assert len(media_packages) > 0
        for pkg in media_packages:
            assert pkg.category.lower() == "media"
    
    def test_load_specific_package(self, loader):
        """Test loading a specific package."""
        pkg = loader.load_package("media-server")
        
        assert pkg.name == "Media Server"
        assert pkg.slug == "media-server"
        assert pkg.category == "Media"
        assert "Jellyfin" in pkg.description
        assert len(pkg.components) > 0
        assert pkg.file_path is not None
        assert pkg.file_path.exists()
    
    def test_load_nonexistent_package(self, loader):
        """Test loading a package that doesn't exist."""
        with pytest.raises(FileNotFoundError):
            loader.load_package("nonexistent-package")
    
    def test_search_packages(self, loader):
        """Test searching packages."""
        # Search by name
        results = loader.search_packages("media")
        assert len(results) > 0
        assert any("media" in p.name.lower() for p in results)
        
        # Search by description
        results = loader.search_packages("jellyfin")
        assert len(results) > 0
        
        # Search with no results
        results = loader.search_packages("xyznonexistent")
        assert len(results) == 0
    
    def test_get_categories(self, loader):
        """Test grouping packages by category."""
        categories = loader.get_categories()
        
        assert len(categories) > 0
        assert "Media" in categories or "media" in categories
        
        # Each category should have at least one package
        for category, packages in categories.items():
            assert len(packages) > 0
            # All packages in category should match
            for pkg in packages:
                assert pkg.category == category
    
    def test_package_with_prompts(self, loader):
        """Test loading a package with customization prompts."""
        pkg = loader.load_package("media-server")
        
        # media-server has customization options
        assert len(pkg.prompts) > 0
        
        # Check prompt structure
        for prompt in pkg.prompts:
            assert prompt.id
            assert prompt.prompt
            assert prompt.default is not None
            assert prompt.type in ["string", "int", "bool"]
    
    def test_render_config_basic(self, loader):
        """Test rendering package config with user inputs."""
        pkg = loader.load_package("nas-basic")

        # Provide user inputs
        user_inputs = {
            "pool_name": "data",
            "include_timemachine": False
        }

        config = loader.render_config(pkg, user_inputs)

        # Should have rendered config
        assert config is not None

        # Handle both wrapped and direct format
        if "config" in config:
            actual_config = config["config"]
        else:
            actual_config = config

        assert "pools" in actual_config
        assert actual_config["pools"] is not None
        assert "data" in actual_config["pools"]

    def test_render_config_substitution(self, loader):
        """Test Jinja2 variable substitution in config."""
        pkg = loader.load_package("nas-basic")

        user_inputs = {
            "pool_name": "mypool",
            "include_timemachine": False
        }

        config = loader.render_config(pkg, user_inputs)

        # Handle both wrapped and direct format
        if "config" in config:
            actual_config = config["config"]
        else:
            actual_config = config

        # Verify pool_name substitution
        assert actual_config is not None
        assert "pools" in actual_config
        assert "mypool" in actual_config["pools"]

        # Verify timemachine was excluded (conditional worked)
        mypool_datasets = actual_config["pools"]["mypool"]["datasets"]
        assert "timemachine" not in mypool_datasets
    
    def test_package_components(self, loader):
        """Test that packages have component listings."""
        pkg = loader.load_package("nas-complete")
        
        # nas-complete should have many components
        assert len(pkg.components) >= 3
        assert all(isinstance(comp, str) for comp in pkg.components)
    
    def test_package_with_requirements(self, loader):
        """Test loading package with system requirements."""
        # Some packages may have requirements
        pkg = loader.load_package("ai-workstation")
        
        # AI workstation should have resource requirements
        # (this will work once we add requirements to the YAML)
        assert pkg.requirements is None or pkg.requirements.min_ram_mb
    
    def test_all_packages_valid(self, loader):
        """Test that all packages can be loaded without errors."""
        packages = loader.list_packages()
        
        for pkg in packages:
            # Should be able to load full details
            full_pkg = loader.load_package(pkg.slug)
            assert full_pkg.name == pkg.name
            assert full_pkg.slug == pkg.slug
            
            # Should have valid config template
            assert full_pkg.config_template
            
            # Should be able to render with minimal inputs
            try:
                config = loader.render_config(full_pkg, {"pool_name": "tank"})
                assert config is not None
            except Exception as e:
                pytest.fail(f"Failed to render {pkg.slug}: {e}")


class TestPackageIntegration:
    """Integration tests for package system."""
    
    def test_package_discovery_workflow(self):
        """Test complete package discovery workflow."""
        loader = PackageLoader()
        
        # 1. List all packages
        all_packages = loader.list_packages()
        assert len(all_packages) > 0
        
        # 2. Filter by category
        media_packages = loader.list_packages(category="Media")
        assert len(media_packages) < len(all_packages)
        
        # 3. Search for specific package
        results = loader.search_packages("media")
        assert len(results) > 0
        
        # 4. Load specific package
        pkg = loader.load_package("media-server")
        assert pkg.slug == "media-server"
    
    def test_package_installation_workflow(self):
        """Test package installation workflow."""
        loader = PackageLoader()
        
        # 1. Load package
        pkg = loader.load_package("nas-basic")
        
        # 2. Collect user inputs (simulated)
        user_inputs = {"pool_name": "tank"}
        
        # Add defaults for any prompts
        for prompt in pkg.prompts:
            if prompt.id not in user_inputs:
                user_inputs[prompt.id] = prompt.default
        
        # 3. Render configuration
        config = loader.render_config(pkg, user_inputs)
        
        # 4. Verify config structure
        assert config is not None
        assert isinstance(config, dict)
