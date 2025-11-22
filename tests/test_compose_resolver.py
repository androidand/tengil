"""Tests for ComposeResolver - multi-strategy compose acquisition."""

import pytest
import yaml

from tengil.services.docker_compose.resolver import ComposeResolver


class TestComposeResolver:
    """Test the compose resolution chain."""
    
    @pytest.fixture
    def resolver(self, tmp_path):
        """Create resolver with temp cache directory."""
        cache_dir = tmp_path / "compose_cache"
        cache_dir.mkdir()
        return ComposeResolver(cache_dir=cache_dir)
    
    @pytest.fixture
    def ollama_cache(self, resolver):
        """Create a cached ollama compose file."""
        cache_path = resolver.cache_dir / "ollama" / "docker-compose.yml"
        cache_path.parent.mkdir(parents=True)
        
        compose = {
            'version': '3.8',
            'services': {
                'ollama': {
                    'image': 'ollama/ollama:latest',
                    'ports': ['11434:11434'],
                    'volumes': ['/root/.ollama:/root/.ollama'],
                    'restart': 'unless-stopped'
                }
            }
        }
        
        with open(cache_path, 'w') as f:
            yaml.dump(compose, f)
        
        return cache_path
    
    def test_strategy_1_cache(self, resolver, ollama_cache):
        """Test Strategy 1: Load from cache."""
        spec = {
            'cache': 'compose_cache/ollama/docker-compose.yml'
        }
        
        result = resolver.resolve(spec)
        
        assert result.source_type == 'cache'
        assert result.content['services']['ollama']['image'] == 'ollama/ollama:latest'
        assert result.metadata['cached'] is True
        assert result.metadata['offline_capable'] is True
    
    def test_strategy_2_fallback_to_image(self, resolver):
        """Test Strategy 2: Generate from image when cache missing."""
        spec = {
            'cache': 'compose_cache/missing/docker-compose.yml',  # Doesn't exist
            'image': 'nginx:alpine',
            'ports': ['80:80'],
            'volumes': ['/data:/usr/share/nginx/html']
        }
        
        result = resolver.resolve(spec)
        
        assert result.source_type == 'image'
        assert result.content['services']['nginx']['image'] == 'nginx:alpine'
        assert result.content['services']['nginx']['ports'] == ['80:80']
        assert result.metadata['generated'] is True
    
    def test_image_generation_with_environment(self, resolver):
        """Test image strategy includes environment variables."""
        spec = {
            'image': 'postgres:15',
            'environment': {
                'POSTGRES_PASSWORD': 'secret',
                'POSTGRES_DB': 'mydb'
            },
            'ports': ['5432:5432']
        }
        
        result = resolver.resolve(spec)
        
        service = result.content['services']['postgres']
        assert service['environment']['POSTGRES_PASSWORD'] == 'secret'
        assert service['environment']['POSTGRES_DB'] == 'mydb'
    
    def test_service_name_extraction(self, resolver):
        """Test service name extraction from various image formats."""
        test_cases = [
            ('ollama/ollama:latest', 'ollama'),
            ('nginx:alpine', 'nginx'),
            ('postgres:15', 'postgres'),
            ('registry.example.com/myapp:v1', 'myapp'),
        ]
        
        for image, expected_name in test_cases:
            name = resolver._service_name_from_image(image)
            assert name == expected_name, f"Failed for {image}"
    
    def test_tengil_labels_added(self, resolver):
        """Test that Tengil metadata labels are added."""
        spec = {
            'image': 'redis:7',
            'ports': ['6379:6379']
        }
        
        result = resolver.resolve(spec)
        
        labels = result.content['services']['redis']['labels']
        assert labels['tengil.managed'] == 'true'
        assert labels['tengil.origin'] == 'image'
        assert labels['tengil.image'] == 'redis:7'
    
    def test_resolution_priority_order(self, resolver, ollama_cache):
        """Test that strategies are tried in priority order."""
        # Spec with cache (highest priority) AND image (fallback)
        spec = {
            'cache': 'compose_cache/ollama/docker-compose.yml',
            'image': 'different/image:latest'  # Should NOT be used
        }
        
        result = resolver.resolve(spec)
        
        # Should use cache, not image
        assert result.source_type == 'cache'
        assert result.content['services']['ollama']['image'] == 'ollama/ollama:latest'
    
    def test_no_valid_source_raises_error(self, resolver):
        """Test that resolution fails with no valid sources."""
        spec = {
            'cache': 'nonexistent.yml'  # Doesn't exist, no fallback
        }
        
        with pytest.raises(ValueError, match="No valid compose source found"):
            resolver.resolve(spec)
    
    def test_save_to_cache(self, resolver):
        """Test saving a working compose to cache."""
        # Generate from image
        spec = {
            'image': 'traefik:latest',
            'ports': ['80:80', '443:443']
        }
        
        result = resolver.resolve(spec)
        
        # Save to cache
        cache_path = resolver.save_to_cache(result, "traefik/docker-compose.yml")
        
        assert cache_path.exists()
        assert cache_path.name == 'docker-compose.yml'
        
        # Verify metadata was saved
        metadata_path = cache_path.parent / "metadata.yml"
        assert metadata_path.exists()
        
        with open(metadata_path) as f:
            metadata = yaml.safe_load(f)
            assert metadata['source_type'] == 'image'
            assert metadata['source_path'] == 'traefik:latest'
    
    def test_cache_with_absolute_path(self, resolver, ollama_cache):
        """Test cache resolution with absolute path."""
        spec = {
            'cache': str(ollama_cache)  # Absolute path
        }
        
        result = resolver.resolve(spec)
        
        assert result.source_type == 'cache'
        assert 'ollama' in result.content['services']
    
    def test_invalid_cache_raises_error(self, resolver, tmp_path):
        """Test that invalid cached compose is logged and falls through."""
        # Create invalid cache file (no services)
        bad_cache = tmp_path / "bad.yml"
        with open(bad_cache, 'w') as f:
            yaml.dump({'version': '3'}, f)  # Missing services
        
        spec = {
            'cache': str(bad_cache)
            # No fallback - should raise error after cache fails
        }
        
        # Should raise "No valid compose source" since cache failed and no fallback
        with pytest.raises(ValueError, match="No valid compose source found"):
            resolver.resolve(spec)
    
    def test_empty_spec_raises_error(self, resolver):
        """Test that empty spec raises error."""
        spec = {}
        
        with pytest.raises(ValueError, match="No valid compose source found"):
            resolver.resolve(spec)


class TestComposeResolverIntegration:
    """Integration tests with real package specs."""
    
    def test_ollama_package_spec(self, tmp_path):
        """Test resolving Ollama package spec."""
        # Setup cache
        cache_dir = tmp_path / "compose_cache"
        ollama_cache = cache_dir / "ollama" / "docker-compose.yml"
        ollama_cache.parent.mkdir(parents=True)
        
        compose = {
            'version': '3.8',
            'services': {
                'ollama': {
                    'image': 'ollama/ollama:latest',
                    'ports': ['11434:11434'],
                    'volumes': ['/root/.ollama:/root/.ollama']
                }
            }
        }
        
        with open(ollama_cache, 'w') as f:
            yaml.dump(compose, f)
        
        resolver = ComposeResolver(cache_dir=cache_dir)
        
        # Actual spec from ai-workstation.yml
        spec = {
            'cache': 'compose_cache/ollama/docker-compose.yml',
            'image': 'ollama/ollama:latest',
            'ports': ['11434:11434'],
            'volumes': ['/root/.ollama:/root/.ollama'],
            'environment': {'OLLAMA_HOST': '0.0.0.0'}
        }
        
        result = resolver.resolve(spec)
        
        assert result.source_type == 'cache'
        assert 'ollama' in result.content['services']
    
    def test_fallback_to_image_generation(self, tmp_path):
        """Test fallback when cache doesn't exist."""
        resolver = ComposeResolver(cache_dir=tmp_path)
        
        spec = {
            'cache': 'compose_cache/missing/docker-compose.yml',
            'image': 'jupyter/scipy-notebook:latest',
            'ports': ['8888:8888'],
            'volumes': ['/home/jovyan/work:/home/jovyan/work'],
            'environment': {'JUPYTER_ENABLE_LAB': 'yes'}
        }
        
        result = resolver.resolve(spec)
        
        # Should fall back to image generation
        assert result.source_type == 'image'
        service = result.content['services']['scipy-notebook']
        assert service['image'] == 'jupyter/scipy-notebook:latest'
        assert service['environment']['JUPYTER_ENABLE_LAB'] == 'yes'
