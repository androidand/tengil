"""Integration tests for scaffold functionality."""

import json
import tempfile
from pathlib import Path

from tengil.scaffold.core import ScaffoldManager


class TestScaffoldIntegration:
    """Test complete scaffold workflows end-to-end."""
    
    def test_scaffold_deployment_script_executable(self):
        """Test that deployment scripts are executable and contain correct server IP."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="test-homelab",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            deploy_script = repo_path / "scripts" / "deploy.sh"
            
            # Check executable permissions
            assert deploy_script.stat().st_mode & 0o111
            
            # Check script contains correct server IP
            script_content = deploy_script.read_text()
            assert "192.168.1.42" in script_content
            assert "rsync" in script_content
            assert "tg diff && tg apply" in script_content
    
    def test_scaffold_security_configuration(self):
        """Test that security files prevent secret leakage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="security-test",
                server_ip="192.168.1.100",
                output_dir=temp_path
            )
            
            # Check .gitignore prevents secret files
            gitignore = (repo_path / ".gitignore").read_text()
            security_patterns = [".env", "*.key", "*.pem", "secrets/", ".tengil.state.json"]
            
            for pattern in security_patterns:
                assert pattern in gitignore, f"Security pattern {pattern} missing from .gitignore"
            
            # Check .env.example provides template
            env_example = (repo_path / ".env.example").read_text()
            assert "DB_PASSWORD=" in env_example
            assert "your_secure_password_here" in env_example
    
    def test_scaffold_nodejs_app_structure(self):
        """Test Node.js app scaffolding creates proper structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="nodejs-test",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["nodejs-api"]
            )
            
            app_path = repo_path / "apps" / "my-nodejs-api"
            
            # Check Node.js files exist
            assert (app_path / "package.json").exists()
            assert (app_path / "app.js").exists()
            
            # Check package.json is valid JSON
            package_json = json.loads((app_path / "package.json").read_text())
            assert package_json["name"] == "my-nodejs-api"
            assert "express" in package_json["dependencies"]
            
            # Check app.js contains basic Express server
            app_js = (app_path / "app.js").read_text()
            assert "express" in app_js
            assert "app.listen" in app_js
    
    def test_scaffold_static_site_structure(self):
        """Test static site scaffolding creates proper structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="static-test",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["static-site"]
            )
            
            app_path = repo_path / "apps" / "my-static-site"
            
            # Check static site files
            assert (app_path / "index.html").exists()
            
            # Check HTML content
            html_content = (app_path / "index.html").read_text()
            assert "<!DOCTYPE html>" in html_content
            assert "my-static-site" in html_content
            assert "Tengil" in html_content
    
    def test_scaffold_tengil_config_valid(self):
        """Test that generated tengil.yml follows current format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="config-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            config_content = (repo_path / "tengil.yml").read_text()
            
            # Check structure follows current Tengil format
            assert "pools:" in config_content
            assert "tank:" in config_content
            assert "type: zfs" in config_content
            assert "datasets:" in config_content
            
            # Check Smart Defaults integration
            assert "profile: appdata" in config_content
            assert "profile: media" in config_content
            assert "profile: documents" in config_content
    
    def test_scaffold_readme_documentation(self):
        """Test that README contains proper documentation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="docs-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            readme_content = (repo_path / "README.md").read_text()
            
            # Check documentation completeness
            assert "docs-test" in readme_content  # Project name
            assert "192.168.1.42" in readme_content  # Server IP
            assert "./scripts/deploy.sh" in readme_content  # Deployment instructions
            assert "Repository Structure" in readme_content  # Structure docs
            assert "Workflow" in readme_content  # Usage workflow
            assert "Security" in readme_content  # Security notes
    
    def test_scaffold_multiple_apps(self):
        """Test scaffolding multiple apps at once."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="multi-app-test",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["nodejs-api", "static-site"]
            )
            
            # Check both apps were created
            assert (repo_path / "apps" / "my-nodejs-api").is_dir()
            assert (repo_path / "apps" / "my-static-site").is_dir()
            
            # Check each app has proper files
            assert (repo_path / "apps" / "my-nodejs-api" / "package.json").exists()
            assert (repo_path / "apps" / "my-static-site" / "index.html").exists()
    
    def test_scaffold_directory_permissions(self):
        """Test that scaffolded directories have proper permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="perms-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            # Check that directories are readable/writable
            for directory in ["apps", "configs", "scripts", "secrets"]:
                dir_path = repo_path / directory
                assert dir_path.is_dir()
                assert dir_path.stat().st_mode & 0o700  # Owner has rwx
    
    def test_scaffold_idempotent(self):
        """Test that scaffolding is idempotent (safe to run twice)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            
            # First scaffold
            repo_path1 = manager.scaffold_homelab(
                name="idempotent-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            # Second scaffold (should not fail)
            repo_path2 = manager.scaffold_homelab(
                name="idempotent-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            assert repo_path1 == repo_path2
            assert (repo_path1 / "tengil.yml").exists()
            assert (repo_path1 / "README.md").exists()


class TestScaffoldErrorHandling:
    """Test error handling in scaffold functionality."""
    
    def test_scaffold_invalid_server_ip(self):
        """Test scaffolding with invalid server IP still works."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            # Should not fail even with invalid IP format
            repo_path = manager.scaffold_homelab(
                name="invalid-ip-test",
                server_ip="not.a.valid.ip",
                output_dir=temp_path
            )
            
            # Should still create repository
            assert repo_path.exists()
            assert (repo_path / "tengil.yml").exists()
            
            # Deploy script should contain the provided IP
            deploy_script = (repo_path / "scripts" / "deploy.sh").read_text()
            assert "not.a.valid.ip" in deploy_script
    
    def test_scaffold_unknown_app_type(self):
        """Test scaffolding with unknown app type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            # Should not fail with unknown app type
            repo_path = manager.scaffold_homelab(
                name="unknown-app-test",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["unknown-app-type"]
            )
            
            # Should still create repository structure
            assert repo_path.exists()
            assert (repo_path / "tengil.yml").exists()
            
            # Unknown app should not create app directory
            assert not (repo_path / "apps" / "my-unknown-app-type").exists()


class TestScaffoldSmartDefaultsIntegration:
    """Test integration with Smart Defaults system."""
    
    def test_scaffold_uses_smart_defaults_profiles(self):
        """Test that scaffolded configs use Smart Defaults profiles."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="smart-defaults-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            config_content = (repo_path / "tengil.yml").read_text()
            
            # Check that Smart Defaults profiles are used
            assert "profile: appdata" in config_content  # For webservices
            assert "profile: media" in config_content    # For websites
            assert "profile: documents" in config_content  # For documents
    
    def test_scaffold_config_works_with_smart_permissions(self):
        """Test that scaffolded config works with Smart Permissions system."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="permissions-test",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["nodejs-api"]
            )
            
            # Load the generated config and test with Smart Permissions
            from tengil.config.loader import ConfigLoader
            
            config_loader = ConfigLoader(str(repo_path / "tengil.yml"))
            config = config_loader.load()
            
            # Should load without errors
            assert "pools" in config
            assert "tank" in config["pools"]
            
            # Should have datasets with profiles
            datasets = config["pools"]["tank"]["datasets"]
            assert "webservices" in datasets
            assert datasets["webservices"]["profile"] == "appdata"