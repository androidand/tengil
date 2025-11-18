"""Configuration validation."""
from typing import Dict, List, Any
from tengil.core.logger import get_logger

logger = get_logger(__name__)

class ConfigValidator:
    """Validates Tengil configuration files."""
    
    REQUIRED_FIELDS = ['pool']
    VALID_PROFILES = ['media', 'documents', 'photos', 'backups', 'dev']
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure and values."""
        self.errors = []
        self.warnings = []
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in config:
                self.errors.append(f"Missing required field: {field}")
        
        # Validate datasets
        if 'datasets' in config:
            for name, dataset in config['datasets'].items():
                self._validate_dataset(name, dataset)
        
        return len(self.errors) == 0
    
    def _validate_dataset(self, name: str, config: Dict[str, Any]):
        """Validate a single dataset configuration."""
        # Check profile
        if 'profile' in config:
            profile = config['profile']
            if profile not in self.VALID_PROFILES:
                self.warnings.append(
                    f"Dataset '{name}': unknown profile '{profile}'. "
                    f"Valid profiles: {', '.join(self.VALID_PROFILES)}"
                )
        
        # Validate ZFS properties
        if 'zfs' in config:
            self._validate_zfs_properties(name, config['zfs'])
        
        # Validate containers
        if 'containers' in config:
            self._validate_containers(name, config['containers'])
        
        # Validate shares
        if 'shares' in config:
            self._validate_shares(name, config['shares'])
    
    def _validate_zfs_properties(self, dataset: str, props: Dict[str, str]):
        """Validate ZFS property values."""
        valid_compression = ['on', 'off', 'lz4', 'lzjb', 'gzip', 'zstd', 'zstd-1', 'zstd-19']
        
        if 'compression' in props:
            comp = props['compression']
            if comp not in valid_compression:
                self.errors.append(
                    f"Dataset '{dataset}': invalid compression '{comp}'"
                )
    
    def _validate_containers(self, dataset: str, containers: List):
        """Validate container mount configurations."""
        if not isinstance(containers, list):
            self.errors.append(f"Dataset '{dataset}': containers must be a list")
            return
        
        for container in containers:
            if isinstance(container, dict):
                if 'name' not in container:
                    self.errors.append(
                        f"Dataset '{dataset}': container missing 'name' field"
                    )
    
    def _validate_shares(self, dataset: str, shares: Dict):
        """Validate NAS share configurations."""
        if not isinstance(shares, dict):
            self.errors.append(f"Dataset '{dataset}': shares must be a dict")
            return
        
        valid_protocols = ['smb', 'nfs']
        for protocol in shares.keys():
            if protocol not in valid_protocols:
                self.warnings.append(
                    f"Dataset '{dataset}': unknown share protocol '{protocol}'"
                )
    
    def get_errors(self) -> List[str]:
        """Return list of validation errors."""
        return self.errors
    
    def get_warnings(self) -> List[str]:
        """Return list of validation warnings."""
        return self.warnings
