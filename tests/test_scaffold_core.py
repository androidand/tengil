"""Tests for homelab repository scaffolding."""

import tempfile
from pathlib import Path

from tengil.scaffold.core import ScaffoldManager


class TestScaffoldManager:
    """Test homelab repository scaffolding."""
    
    def test_scaffold_basic_homelab(self):
        """Test scaffolding a basic homelab repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="test-homelab",
                server_ip="192.168.1.42",
                template="basic",
                output_dir=temp_path
            )
            
            # Check directory structure
            assert repo_path.exists()
            assert (repo_path / "tengil.yml").exists()
            assert (repo_path / "apps").is_dir()
            assert (repo_path / "scripts").is_dir()
            assert (repo_path / "configs").is_dir()
            
            # Check generated files
            assert (repo_path / "scripts" / "deploy.sh").exists()
            assert (repo_path / ".gitignore").exists()
            assert (repo_path / ".env.example").exists()
            assert (repo_path / "README.md").exists()
            
            # Check deploy script is executable
            deploy_script = repo_path / "scripts" / "deploy.sh"
            assert deploy_script.stat().st_mode & 0o111  # Has execute permission
    
    def test_scaffold_with_apps(self):
        """Test scaffolding with application templates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="test-homelab",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["nodejs-api", "static-site"]
            )
            
            # Check app scaffolding
            assert (repo_path / "apps" / "my-nodejs-api").is_dir()
            assert (repo_path / "apps" / "my-nodejs-api" / "package.json").exists()
            assert (repo_path / "apps" / "my-nodejs-api" / "app.js").exists()
            
            assert (repo_path / "apps" / "my-static-site").is_dir()
            assert (repo_path / "apps" / "my-static-site" / "index.html").exists()
    
    def test_generated_config_valid(self):
        """Test that generated tengil.yml is valid."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="test-homelab",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            # Check tengil.yml content
            config_content = (repo_path / "tengil.yml").read_text()
            assert "pools:" in config_content
            assert "webservices:" in config_content
            assert "profile: appdata" in config_content
    
    def test_security_files_generated(self):
        """Test that security files are properly generated."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="test-homelab", 
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            # Check .gitignore
            gitignore_content = (repo_path / ".gitignore").read_text()
            assert ".env" in gitignore_content
            assert "secrets/" in gitignore_content
            assert ".tengil.state.json" in gitignore_content
            
            # Check .env.example
            env_example = (repo_path / ".env.example").read_text()
            assert "DB_PASSWORD=" in env_example
            assert "API_KEY=" in env_example