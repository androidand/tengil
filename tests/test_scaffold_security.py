"""Security-focused tests for scaffold functionality."""

import tempfile
from pathlib import Path

import pytest

from tengil.scaffold.core import ScaffoldManager


class TestScaffoldSecurity:
    """Test security aspects of scaffolding."""
    
    def test_gitignore_prevents_secret_leakage(self):
        """Test that .gitignore prevents common secret files from being committed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="security-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            gitignore_content = (repo_path / ".gitignore").read_text()
            
            # Critical security patterns
            critical_patterns = [
                ".env",           # Environment variables
                "*.key",          # Private keys
                "*.pem",          # Certificates
                "secrets/",       # Secret directories
                ".tengil.state.json",  # State files with potential secrets
            ]
            
            for pattern in critical_patterns:
                assert pattern in gitignore_content, f"Critical security pattern {pattern} missing"
            
            # Additional security patterns
            additional_patterns = [
                "__pycache__/",   # Python cache
                "*.pyc",          # Python bytecode
                ".DS_Store",      # macOS metadata
            ]
            
            for pattern in additional_patterns:
                assert pattern in gitignore_content, f"Security pattern {pattern} missing"
    
    def test_env_example_no_real_secrets(self):
        """Test that .env.example contains only placeholder values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="env-security-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            env_example = (repo_path / ".env.example").read_text()
            
            # Should contain placeholder patterns
            placeholder_patterns = [
                "your_secure_password_here",
                "your_api_key_here",
                "admin_password",
            ]
            
            for pattern in placeholder_patterns:
                assert pattern in env_example, f"Placeholder {pattern} missing from .env.example"
            
            # Should NOT contain real-looking secrets
            dangerous_patterns = [
                "sk-",           # OpenAI API keys
                "ghp_",          # GitHub personal access tokens
                "xoxb-",         # Slack bot tokens
                "AKIA",          # AWS access keys
                "password123",   # Weak passwords
                "admin123",      # Weak admin passwords
            ]
            
            for pattern in dangerous_patterns:
                assert pattern not in env_example, f"Dangerous pattern {pattern} found in .env.example"
    
    def test_deploy_script_no_hardcoded_secrets(self):
        """Test that deployment scripts don't contain hardcoded secrets."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="deploy-security-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            deploy_script = (repo_path / "scripts" / "deploy.sh").read_text()
            
            # Should exclude secrets from rsync
            assert "--exclude='.env'" in deploy_script
            assert "--exclude='secrets/'" in deploy_script
            
            # Should not contain hardcoded credentials
            dangerous_patterns = [
                "password=",
                "token=",
                "secret=",
                "key=",
            ]
            
            for pattern in dangerous_patterns:
                assert pattern not in deploy_script.lower(), f"Potential secret {pattern} in deploy script"
    
    def test_file_permissions_secure(self):
        """Test that generated files have secure permissions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="perms-security-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            # Deploy script should be executable by owner only
            deploy_script = repo_path / "scripts" / "deploy.sh"
            mode = deploy_script.stat().st_mode
            
            # Should be executable by owner
            assert mode & 0o100, "Deploy script not executable by owner"
            
            # Should not be world-writable
            assert not (mode & 0o002), "Deploy script is world-writable (security risk)"
    
    def test_secrets_directory_created_empty(self):
        """Test that secrets directory is created but empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="secrets-dir-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            secrets_dir = repo_path / "secrets"
            
            # Directory should exist
            assert secrets_dir.exists()
            assert secrets_dir.is_dir()
            
            # Directory should be empty (no default secrets)
            assert len(list(secrets_dir.iterdir())) == 0, "Secrets directory should be empty"
    
    def test_readme_contains_security_guidance(self):
        """Test that README contains security best practices."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="readme-security-test",
                server_ip="192.168.1.42",
                output_dir=temp_path
            )
            
            readme_content = (repo_path / "README.md").read_text()
            
            # Should contain security section
            assert "Security" in readme_content
            
            # Should mention key security practices
            security_topics = [
                ".env",           # Environment file mentioned
                "not committed", # Secrets not committed
                "SSH keys",      # SSH authentication
                ".env.example",  # Template file
            ]
            
            for topic in security_topics:
                assert topic in readme_content, f"Security topic '{topic}' missing from README"
    
    def test_no_default_passwords_in_configs(self):
        """Test that no default passwords are included in any configs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            repo_path = manager.scaffold_homelab(
                name="password-security-test",
                server_ip="192.168.1.42",
                output_dir=temp_path,
                apps=["nodejs-api", "static-site"]
            )
            
            # Check all generated files for default passwords
            dangerous_passwords = [
                "password",
                "123456",
                "admin",
                "root",
                "changeme",
                "default",
            ]
            
            # Scan all text files
            for file_path in repo_path.rglob("*"):
                if file_path.is_file() and file_path.suffix in [".yml", ".yaml", ".json", ".js", ".py", ".sh", ".md"]:
                    try:
                        content = file_path.read_text().lower()
                        for password in dangerous_passwords:
                            # Allow in comments/documentation but not as values
                            if f'"{password}"' in content or f"'{password}'" in content or f"={password}" in content:
                                pytest.fail(f"Dangerous default password '{password}' found in {file_path}")
                    except UnicodeDecodeError:
                        # Skip binary files
                        continue


class TestScaffoldValidation:
    """Test input validation for scaffold functionality."""
    
    def test_scaffold_validates_server_ip_format(self):
        """Test that scaffold validates server IP format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            
            # Should handle various IP formats gracefully
            test_ips = [
                "192.168.1.42",      # Valid IP
                "10.0.0.1",          # Valid private IP
                "homelab.local",     # Hostname
                "192.168.1.42:22",   # IP with port (should work)
            ]
            
            for ip in test_ips:
                repo_path = manager.scaffold_homelab(
                    name=f"ip-test-{ip.replace('.', '-').replace(':', '-')}",
                    server_ip=ip,
                    output_dir=temp_path
                )
                
                # Should create repository regardless of IP format
                assert repo_path.exists()
                
                # Deploy script should contain the IP
                deploy_script = (repo_path / "scripts" / "deploy.sh").read_text()
                assert ip in deploy_script
    
    def test_scaffold_validates_name_format(self):
        """Test that scaffold handles various name formats."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            manager = ScaffoldManager()
            
            # Test various name formats
            test_names = [
                "my-homelab",        # Hyphenated
                "homelab123",        # With numbers
                "andreas_homelab",   # Underscored
            ]
            
            for name in test_names:
                repo_path = manager.scaffold_homelab(
                    name=name,
                    server_ip="192.168.1.42",
                    output_dir=temp_path
                )
                
                # Should create directory with exact name
                assert repo_path.name == name
                assert repo_path.exists()
                
                # README should contain the name
                readme_content = (repo_path / "README.md").read_text()
                assert name in readme_content