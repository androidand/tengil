"""App configuration models for git-based app deployment."""
import re
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import List, Optional, Dict, Literal, Any


class AppSource(BaseModel):
    """Source code configuration for an app."""

    model_config = ConfigDict(extra='forbid')

    type: Literal["git", "docker", "local"] = "git"
    url: Optional[str] = None
    branch: str = "main"
    path: str = "/app"  # Where to clone/mount inside container

    @model_validator(mode='after')
    def validate_url_required(self) -> 'AppSource':
        """Validate URL is provided for git/docker sources and check format."""
        if self.type == 'git':
            if not self.url:
                raise ValueError("Git source requires url to be specified")
            if not self.url.startswith(('https://', 'git@', 'http://')):
                raise ValueError(
                    f"Git URL must start with https://, git@, or http://. Got: {self.url}"
                )
        elif self.type == 'docker':
            if not self.url:
                raise ValueError("Docker source requires url (image) to be specified")
        return self


class AppRuntime(BaseModel):
    """Runtime environment configuration for an app."""

    model_config = ConfigDict(extra='forbid')

    secrets: List[str] = Field(default_factory=list, description="Environment variable names to inject from host env")
    packages: List[str] = Field(default_factory=list, description="System packages to install (e.g., nodejs, npm, git)")
    startup_command: Optional[str] = Field(None, description="Command to run after deployment")
    healthcheck: Optional[Dict[str, Any]] = Field(None, description="Optional healthcheck configuration")

    @field_validator('secrets')
    @classmethod
    def validate_secrets(cls, v):
        """Validate secret names are valid environment variable names."""
        for secret in v:
            if not re.match(r'^[A-Z_][A-Z0-9_]*$', secret):
                raise ValueError(
                    f"Secret name '{secret}' is not a valid env var name. "
                    "Must be uppercase letters, numbers, and underscores only."
                )
        return v

    @field_validator('packages')
    @classmethod
    def validate_packages(cls, v):
        """Validate package names."""
        for package in v:
            if not re.match(r'^[a-z0-9\-\.+]+$', package):
                raise ValueError(
                    f"Package name '{package}' contains invalid characters. "
                    "Must be lowercase letters, numbers, hyphens, dots, and plus signs."
                )
        return v


class AppStorage(BaseModel):
    """Storage mount configuration for an app."""

    model_config = ConfigDict(extra='forbid')

    mount: str = Field(..., description="Mount point inside container")
    profile: str = Field("dev", description="ZFS profile to use")
    size: str = Field("10G", description="Dataset size")

    @field_validator('mount')
    @classmethod
    def validate_mount(cls, v):
        """Validate mount path is absolute."""
        if not v.startswith('/'):
            raise ValueError(f"Mount path must be absolute (start with /). Got: {v}")
        return v

    @field_validator('size')
    @classmethod
    def validate_size(cls, v):
        """Validate size format."""
        if not re.match(r'^\d+[KMGT]$', v):
            raise ValueError(
                f"Size must be in format like '10G', '500M', '1T'. Got: {v}"
            )
        return v


class AppConfig(BaseModel):
    """Complete app configuration.

    This represents a deployable application with its container requirements,
    source code location, runtime configuration, and storage needs.
    """

    model_config = ConfigDict(
        extra='forbid',
        json_schema_extra={
            "example": {
                "name": "node-api-server",
                "description": "Custom Node.js REST API",
                "container": {
                    "template": "debian-12-standard",
                    "pool": "production",
                    "memory": 2048,
                    "cores": 2,
                    "network": {
                        "ip": "192.168.1.100/24",
                        "gateway": "192.168.1.1"
                    }
                },
                "source": {
                    "type": "git",
                    "url": "https://github.com/myorg/api-server",
                    "branch": "main",
                    "path": "/app"
                },
                "runtime": {
                    "secrets": ["NODE_ENV", "DATABASE_URL", "JWT_SECRET"],
                    "packages": ["nodejs", "npm", "git"],
                    "startup_command": "cd /app && npm install && npm start"
                },
                "storage": [
                    {
                        "mount": "/data",
                        "profile": "dev",
                        "size": "10G"
                    }
                ]
            }
        }
    )

    name: str = Field(..., description="App name (becomes container hostname)")
    description: Optional[str] = Field(None, description="Human-readable description")

    # Container configuration (reuses existing ContainerMount structure internally)
    container: Dict[str, Any] = Field(..., description="Container configuration")

    # App-specific configuration
    source: Optional[AppSource] = Field(None, description="Source code configuration")
    runtime: Optional[AppRuntime] = Field(None, description="Runtime environment")
    storage: List[AppStorage] = Field(default_factory=list, description="Additional storage mounts")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate name is a valid hostname."""
        if not re.match(r'^[a-z0-9]([a-z0-9\-]*[a-z0-9])?$', v):
            raise ValueError(
                f"Name '{v}' is not a valid hostname. "
                "Must be lowercase alphanumeric with hyphens, "
                "start and end with alphanumeric."
            )
        if len(v) > 63:
            raise ValueError(f"Name '{v}' is too long (max 63 characters)")
        return v

    @model_validator(mode='after')
    def validate_container_and_set_hostname(self) -> 'AppConfig':
        """Ensure container config has template and auto-set hostname."""
        if 'template' not in self.container:
            raise ValueError("Container configuration must specify a template")

        # Auto-set hostname to app name if not specified
        if 'hostname' not in self.container:
            self.container['hostname'] = self.name

        return self
