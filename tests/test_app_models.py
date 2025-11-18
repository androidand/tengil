"""Tests for app configuration models."""
import pytest
from pydantic import ValidationError

from tengil.models.app import AppSource, AppRuntime, AppStorage, AppConfig


class TestAppSource:
    """Test AppSource model validation."""

    def test_valid_git_source(self):
        """Test valid git source configuration."""
        source = AppSource(
            type="git",
            url="https://github.com/user/repo",
            branch="main",
            path="/app"
        )
        assert source.type == "git"
        assert source.url == "https://github.com/user/repo"
        assert source.branch == "main"
        assert source.path == "/app"

    def test_git_source_with_ssh_url(self):
        """Test git source with SSH URL."""
        source = AppSource(
            type="git",
            url="git@github.com:user/repo.git",
            branch="develop"
        )
        assert source.url == "git@github.com:user/repo.git"

    def test_git_source_without_url_fails(self):
        """Test that git source without URL fails validation."""
        with pytest.raises(ValidationError, match="Git source requires url"):
            AppSource(type="git", branch="main")

    def test_docker_source(self):
        """Test docker source configuration."""
        source = AppSource(
            type="docker",
            url="nginx:latest",
            path="/usr/share/nginx/html"
        )
        assert source.type == "docker"
        assert source.url == "nginx:latest"

    def test_docker_source_without_url_fails(self):
        """Test that docker source without URL fails."""
        with pytest.raises(ValidationError, match="Docker source requires url"):
            AppSource(type="docker")

    def test_local_source(self):
        """Test local source configuration."""
        source = AppSource(type="local", path="/opt/myapp")
        assert source.type == "local"
        assert source.path == "/opt/myapp"

    def test_invalid_git_url_fails(self):
        """Test that invalid git URL fails validation."""
        with pytest.raises(ValidationError, match="Git URL must start with"):
            AppSource(type="git", url="invalid-url")

    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValidationError):
            AppSource(type="git", url="https://github.com/user/repo", extra_field="value")


class TestAppRuntime:
    """Test AppRuntime model validation."""

    def test_valid_runtime(self):
        """Test valid runtime configuration."""
        runtime = AppRuntime(
            secrets=["DATABASE_URL", "API_KEY"],
            packages=["nodejs", "npm", "git"],
            startup_command="npm start"
        )
        assert runtime.secrets == ["DATABASE_URL", "API_KEY"]
        assert runtime.packages == ["nodejs", "npm", "git"]
        assert runtime.startup_command == "npm start"

    def test_empty_runtime(self):
        """Test runtime with no configuration."""
        runtime = AppRuntime()
        assert runtime.secrets == []
        assert runtime.packages == []
        assert runtime.startup_command is None

    def test_invalid_secret_name_fails(self):
        """Test that invalid secret names fail validation."""
        with pytest.raises(ValidationError, match="not a valid env var name"):
            AppRuntime(secrets=["invalid-name"])

    def test_lowercase_secret_name_fails(self):
        """Test that lowercase secret names fail validation."""
        with pytest.raises(ValidationError, match="not a valid env var name"):
            AppRuntime(secrets=["database_url"])

    def test_valid_secret_names(self):
        """Test various valid secret name formats."""
        runtime = AppRuntime(
            secrets=[
                "DATABASE_URL",
                "API_KEY",
                "JWT_SECRET_KEY",
                "AWS_ACCESS_KEY_ID",
                "NODE_ENV"
            ]
        )
        assert len(runtime.secrets) == 5

    def test_invalid_package_name_fails(self):
        """Test that invalid package names fail validation."""
        with pytest.raises(ValidationError, match="contains invalid characters"):
            AppRuntime(packages=["Node.JS"])  # Uppercase not allowed

    def test_valid_package_names(self):
        """Test various valid package name formats."""
        runtime = AppRuntime(
            packages=[
                "nodejs",
                "npm",
                "git",
                "build-essential",
                "python3.11",
                "libc++1"
            ]
        )
        assert len(runtime.packages) == 6

    def test_healthcheck_optional(self):
        """Test that healthcheck is optional."""
        runtime = AppRuntime(
            healthcheck={
                "type": "http",
                "url": "http://localhost:3000/health",
                "interval": "30s"
            }
        )
        assert runtime.healthcheck is not None

    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValidationError):
            AppRuntime(secrets=[], extra_field="value")


class TestAppStorage:
    """Test AppStorage model validation."""

    def test_valid_storage(self):
        """Test valid storage configuration."""
        storage = AppStorage(
            mount="/data",
            profile="dev",
            size="10G"
        )
        assert storage.mount == "/data"
        assert storage.profile == "dev"
        assert storage.size == "10G"

    def test_storage_defaults(self):
        """Test storage default values."""
        storage = AppStorage(mount="/data")
        assert storage.profile == "dev"
        assert storage.size == "10G"

    def test_relative_mount_fails(self):
        """Test that relative mount paths fail validation."""
        with pytest.raises(ValidationError, match="must be absolute"):
            AppStorage(mount="data")

    def test_invalid_size_format_fails(self):
        """Test that invalid size formats fail validation."""
        with pytest.raises(ValidationError, match="Size must be in format"):
            AppStorage(mount="/data", size="10GB")

    def test_valid_size_formats(self):
        """Test various valid size formats."""
        for size in ["512M", "10G", "1T", "100K"]:
            storage = AppStorage(mount="/data", size=size)
            assert storage.size == size

    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValidationError):
            AppStorage(mount="/data", extra_field="value")


class TestAppConfig:
    """Test AppConfig model validation."""

    def test_valid_app_config(self):
        """Test valid complete app configuration."""
        config = AppConfig(
            name="node-api",
            description="Node.js API server",
            container={
                "template": "debian-12-standard",
                "pool": "production",
                "memory": 2048,
                "cores": 2
            },
            source=AppSource(
                type="git",
                url="https://github.com/user/api",
                branch="main"
            ),
            runtime=AppRuntime(
                secrets=["DATABASE_URL"],
                packages=["nodejs", "npm"]
            )
        )
        assert config.name == "node-api"
        assert config.container["template"] == "debian-12-standard"

    def test_minimal_app_config(self):
        """Test minimal app configuration."""
        config = AppConfig(
            name="simple-app",
            container={"template": "debian-12-standard"}
        )
        assert config.name == "simple-app"
        assert config.source is None
        assert config.runtime is None
        assert config.storage == []

    def test_invalid_name_fails(self):
        """Test that invalid app names fail validation."""
        invalid_names = [
            "Node-API",  # Uppercase
            "node_api",  # Underscore
            "node api",  # Space
            "-nodeapi",  # Starts with hyphen
            "nodeapi-",  # Ends with hyphen
            "a" * 64,    # Too long
        ]
        for name in invalid_names:
            with pytest.raises(ValidationError):
                AppConfig(
                    name=name,
                    container={"template": "debian-12-standard"}
                )

    def test_valid_names(self):
        """Test various valid app names."""
        valid_names = [
            "app",
            "my-app",
            "api-server",
            "node-api-v2",
            "a" * 63,  # Max length
        ]
        for name in valid_names:
            config = AppConfig(
                name=name,
                container={"template": "debian-12-standard"}
            )
            assert config.name == name

    def test_container_without_template_fails(self):
        """Test that container config without template fails."""
        with pytest.raises(ValidationError, match="must specify a template"):
            AppConfig(
                name="test",
                container={"memory": 2048}
            )

    def test_hostname_auto_set_from_name(self):
        """Test that hostname is auto-set to app name."""
        config = AppConfig(
            name="my-app",
            container={"template": "debian-12-standard"}
        )
        assert config.container["hostname"] == "my-app"

    def test_explicit_hostname_preserved(self):
        """Test that explicit hostname is preserved."""
        config = AppConfig(
            name="my-app",
            container={
                "template": "debian-12-standard",
                "hostname": "custom-hostname"
            }
        )
        assert config.container["hostname"] == "custom-hostname"

    def test_full_app_config_example(self):
        """Test the full example from schema."""
        config = AppConfig(
            name="node-api-server",
            description="Custom Node.js REST API",
            container={
                "template": "debian-12-standard",
                "pool": "production",
                "memory": 2048,
                "cores": 2,
                "network": {
                    "ip": "192.168.1.100/24",
                    "gateway": "192.168.1.1"
                }
            },
            source=AppSource(
                type="git",
                url="https://github.com/myorg/api-server",
                branch="main",
                path="/app"
            ),
            runtime=AppRuntime(
                secrets=["NODE_ENV", "DATABASE_URL", "JWT_SECRET"],
                packages=["nodejs", "npm", "git"],
                startup_command="cd /app && npm install && npm start"
            ),
            storage=[
                AppStorage(mount="/data", profile="dev", size="10G")
            ]
        )
        assert config.name == "node-api-server"
        assert config.source.url == "https://github.com/myorg/api-server"
        assert len(config.runtime.secrets) == 3
        assert len(config.storage) == 1

    def test_extra_fields_forbidden(self):
        """Test that extra fields are not allowed."""
        with pytest.raises(ValidationError):
            AppConfig(
                name="test",
                container={"template": "debian-12-standard"},
                extra_field="value"
            )


class TestAppConfigIntegration:
    """Integration tests for app config models."""

    def test_parse_from_dict(self):
        """Test parsing app config from dictionary."""
        data = {
            "name": "jellyfin",
            "description": "Media server",
            "container": {
                "template": "debian-12-standard",
                "memory": 8192,
                "cores": 4,
                "pool": "production"
            },
            "source": {
                "type": "git",
                "url": "https://github.com/jellyfin/jellyfin-web",
                "branch": "master",
                "path": "/app"
            },
            "runtime": {
                "secrets": ["JELLYFIN_API_KEY"],
                "packages": ["nodejs", "npm", "ffmpeg"],
                "startup_command": "cd /app && npm start"
            }
        }
        config = AppConfig(**data)
        assert config.name == "jellyfin"
        assert config.container["hostname"] == "jellyfin"

    def test_dict_roundtrip(self):
        """Test that config can be converted to dict and back."""
        config = AppConfig(
            name="test-app",
            container={"template": "debian-12-standard"},
            source=AppSource(
                type="git",
                url="https://github.com/user/repo"
            )
        )
        data = config.model_dump()
        config2 = AppConfig(**data)
        assert config2.name == config.name
        assert config2.source.url == config.source.url
