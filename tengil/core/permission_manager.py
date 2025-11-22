"""Unified permission management for datasets, containers, and shares.

The killer feature: automatically manage permissions across:
- ZFS ACLs
- Container mount flags (readonly vs readwrite)
- Samba share permissions
- User/group mappings

Instead of manually configuring each layer, just declare consumers:
    datasets:
      media:
        consumers:
          - type: container
            name: jellyfin
            access: read
          - type: container
            name: immich
            access: write
          - type: share
            protocol: smb
            name: Media
            access: read

Tengil generates all the necessary permissions automatically.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class AccessLevel(Enum):
    """Access level for a consumer."""
    READ = "read"
    WRITE = "write"
    NONE = "none"


class ConsumerType(Enum):
    """Type of consumer accessing a dataset."""
    CONTAINER = "container"
    SHARE_SMB = "smb"
    SHARE_NFS = "nfs"
    USER = "user"
    GROUP = "group"


@dataclass
class Consumer:
    """A consumer that accesses a dataset."""
    type: ConsumerType
    name: str
    access: AccessLevel
    readonly: bool = False  # Computed from access level
    
    def __post_init__(self):
        """Compute readonly flag from access level."""
        self.readonly = (self.access == AccessLevel.READ)


@dataclass
class PermissionSet:
    """Complete permission configuration for a dataset."""
    dataset_path: str
    owner_user: str = "root"
    owner_group: str = "root"
    base_permissions: str = "755"  # Default directory permissions
    consumers: List[Consumer] = None
    
    def __post_init__(self):
        if self.consumers is None:
            self.consumers = []
    
    @property
    def needs_write_access(self) -> bool:
        """Check if any consumer needs write access."""
        return any(c.access == AccessLevel.WRITE for c in self.consumers)
    
    @property
    def container_consumers(self) -> List[Consumer]:
        """Get all container consumers."""
        return [c for c in self.consumers if c.type == ConsumerType.CONTAINER]
    
    @property
    def smb_consumers(self) -> List[Consumer]:
        """Get all SMB share consumers."""
        return [c for c in self.consumers if c.type == ConsumerType.SHARE_SMB]
    
    @property
    def nfs_consumers(self) -> List[Consumer]:
        """Get all NFS export consumers."""
        return [c for c in self.consumers if c.type == ConsumerType.SHARE_NFS]


class PermissionConflict(Exception):
    """Raised when there's a permission conflict."""
    pass


class PermissionManager:
    """Manages unified permissions across ZFS, containers, and shares."""
    
    def __init__(self, mock: bool = False):
        """Initialize permission manager.
        
        Args:
            mock: If True, don't apply changes (for testing)
        """
        self.mock = mock
        self.permission_sets: Dict[str, PermissionSet] = {}
    
    @staticmethod
    def _normalize_dataset_path(path: str) -> str:
        """Normalize dataset path (remove leading slash if present).
        
        Args:
            path: Dataset path (e.g., '/tank/media' or 'tank/media')
        
        Returns:
            Normalized path without leading slash (e.g., 'tank/media')
        """
        return path.lstrip('/')
    
    def register_dataset(self, dataset_path: str, 
                        owner_user: str = "root",
                        owner_group: str = "root") -> PermissionSet:
        """Register a dataset for permission management.
        
        Args:
            dataset_path: Full ZFS dataset path (e.g., tank/media or /tank/media)
            owner_user: Dataset owner user
            owner_group: Dataset owner group
        
        Returns:
            PermissionSet for the dataset
        """
        dataset_path = self._normalize_dataset_path(dataset_path)
        
        if dataset_path in self.permission_sets:
            return self.permission_sets[dataset_path]
        
        perm_set = PermissionSet(
            dataset_path=dataset_path,
            owner_user=owner_user,
            owner_group=owner_group
        )
        self.permission_sets[dataset_path] = perm_set
        logger.debug(f"Registered dataset: {dataset_path}")
        return perm_set
    
    def add_consumer(self, dataset_path: str, consumer_type: ConsumerType,
                    name: str, access: AccessLevel) -> Consumer:
        """Add a consumer to a dataset.
        
        Args:
            dataset_path: Full ZFS dataset path (with or without leading slash)
            consumer_type: Type of consumer (container, share, etc.)
            name: Consumer name/identifier
            access: Access level (read, write)
        
        Returns:
            Created Consumer object
        
        Raises:
            PermissionConflict: If there's a conflicting permission
        """
        dataset_path = self._normalize_dataset_path(dataset_path)
        
        perm_set = self.permission_sets.get(dataset_path)
        if not perm_set:
            perm_set = self.register_dataset(dataset_path)
        
        existing = self._find_existing_consumer(perm_set, consumer_type, name)
        if existing:
            if existing.access == access:
                logger.debug(
                    "Consumer %s (%s) already registered for %s - skipping",
                    name,
                    consumer_type.value,
                    dataset_path,
                )
                return existing
            raise PermissionConflict(
                f"{name} already has {existing.access.value} access, "
                f"cannot also have {access.value} access"
            )
        
        # Check for other conflicts (e.g. future cross-consumer rules)
        conflicts = self._check_conflicts(perm_set, consumer_type, name, access)
        if conflicts:
            raise PermissionConflict(
                f"Permission conflict on {dataset_path}: {conflicts}"
            )
        
        consumer = Consumer(
            type=consumer_type,
            name=name,
            access=access
        )
        perm_set.consumers.append(consumer)
        
        logger.info(
            f"Added consumer: {name} ({consumer_type.value}) "
            f"with {access.value} access to {dataset_path}"
        )
        return consumer
    
    def _check_conflicts(self, perm_set: PermissionSet, 
                        consumer_type: ConsumerType,
                        name: str, access: AccessLevel) -> Optional[str]:
        """Check for permission conflicts.
        
        Conflicts include:
        - Multiple containers wanting different access levels to same mount
        - Read-only share but write-enabled container
        
        Args:
            perm_set: Permission set to check
            consumer_type: New consumer type
            name: New consumer name
            access: Requested access level
        
        Returns:
            Conflict description or None
        """
        # Placeholder for future cross-consumer conflict detection
        return None
    
    def get_container_mount_flags(self, dataset_path: str, 
                                  container_name: str) -> Dict[str, any]:
        """Get mount flags for a container.
        
        Args:
            dataset_path: Full ZFS dataset path (with or without leading slash)
            container_name: Container name
        
        Returns:
            Dict with mount configuration:
                - readonly: bool
                - mount_point: str (e.g., /media)
        """
        dataset_path = self._normalize_dataset_path(dataset_path)
        perm_set = self.permission_sets.get(dataset_path)
        if not perm_set:
            logger.warning(f"No permission set for {dataset_path}")
            return {"readonly": True}
        
        # Find this container in consumers
        for consumer in perm_set.container_consumers:
            if consumer.name == container_name:
                return {
                    "readonly": consumer.readonly,
                    "access": consumer.access.value
                }
        
        # Default to readonly if not found
        logger.warning(
            f"Container {container_name} not found in consumers "
            f"for {dataset_path}, defaulting to readonly"
        )
        return {"readonly": True}
    
    def get_zfs_acl_commands(self, dataset_path: str) -> List[str]:
        """Generate ZFS ACL commands for a dataset.
        
        Args:
            dataset_path: Full ZFS dataset path (with or without leading slash)
        
        Returns:
            List of shell commands to set ACLs
        """
        dataset_path = self._normalize_dataset_path(dataset_path)
        perm_set = self.permission_sets.get(dataset_path)
        if not perm_set:
            return []
        
        commands = []
        mount_path = f"/{dataset_path}"  # Simplified, should lookup actual mount
        
        # Set owner
        commands.append(
            f"chown {perm_set.owner_user}:{perm_set.owner_group} {mount_path}"
        )
        
        # Set base permissions
        if perm_set.needs_write_access:
            # Multiple writers need group write
            commands.append(f"chmod 775 {mount_path}")
        else:
            # Read-only consumers
            commands.append(f"chmod 755 {mount_path}")
        
        # TODO: Add more sophisticated ACLs for multiple users/groups
        
        return commands
    
    def get_smb_share_config(self, dataset_path: str, 
                           share_name: str) -> Dict[str, str]:
        """Generate Samba share configuration.
        
        Args:
            dataset_path: Full ZFS dataset path (with or without leading slash)
            share_name: SMB share name
        
        Returns:
            Dict with Samba configuration options
        """
        dataset_path = self._normalize_dataset_path(dataset_path)
        perm_set = self.permission_sets.get(dataset_path)
        if not perm_set:
            return {}
        
        # Find SMB consumer for this share
        smb_consumer = None
        for consumer in perm_set.smb_consumers:
            if consumer.name == share_name:
                smb_consumer = consumer
                break
        
        if not smb_consumer:
            logger.warning(f"No SMB consumer found for share {share_name}")
            return {}
        
        # Generate Samba config
        config = {
            "path": f"/{dataset_path}",
            "browseable": "yes",
            "guest ok": "no",
            "valid users": "@users",  # TODO: Make configurable
        }
        
        # Set write permissions based on access level
        if smb_consumer.access == AccessLevel.WRITE:
            config["read only"] = "no"
            config["writable"] = "yes"
        else:
            config["read only"] = "yes"
            config["writable"] = "no"
        
        return config
    
    def validate_all(self) -> List[str]:
        """Validate all permission sets for conflicts.
        
        Returns:
            List of warnings/errors (empty if no issues)
        """
        issues = []
        
        for dataset_path, perm_set in self.permission_sets.items():
            # Check for conflicting access patterns
            has_write = any(
                c.access == AccessLevel.WRITE 
                for c in perm_set.consumers
            )
            has_read = any(
                c.access == AccessLevel.READ 
                for c in perm_set.consumers
            )
            
            if has_write and has_read:
                writer_names = [
                    c.name for c in perm_set.consumers 
                    if c.access == AccessLevel.WRITE
                ]
                reader_names = [
                    c.name for c in perm_set.consumers 
                    if c.access == AccessLevel.READ
                ]
                issues.append(
                    f"⚠️  {dataset_path}: Mixed access - "
                    f"writers: {', '.join(writer_names)}, "
                    f"readers: {', '.join(reader_names)}"
                )
        
        return issues
    
    def generate_summary(self) -> str:
        """Generate a summary of all permissions.
        
        Returns:
            Human-readable summary string
        """
        if not self.permission_sets:
            return "No permission sets configured"
        
        lines = ["Permission Summary:"]
        for dataset_path, perm_set in sorted(self.permission_sets.items()):
            lines.append(f"\n  {dataset_path}:")
            lines.append(f"    Owner: {perm_set.owner_user}:{perm_set.owner_group}")
            
            if perm_set.container_consumers:
                lines.append("    Containers:")
                for c in perm_set.container_consumers:
                    flag = "ro" if c.readonly else "rw"
                    lines.append(f"      - {c.name} ({flag})")
            
            if perm_set.smb_consumers:
                lines.append("    SMB Shares:")
                for c in perm_set.smb_consumers:
                    access = "read-only" if c.readonly else "read-write"
                    lines.append(f"      - {c.name} ({access})")
            
            if perm_set.nfs_consumers:
                lines.append("    NFS Exports:")
                for c in perm_set.nfs_consumers:
                    access = "ro" if c.readonly else "rw"
                    lines.append(f"      - {c.name} ({access})")
        
        return "\n".join(lines)

    def load_from_config(self, datasets: Dict[str, Dict[str, Any]]) -> None:
        """Register datasets and consumers from configuration structures.
        
        Args:
            datasets: Mapping of dataset path -> dataset configuration dict
        """
        for dataset_path, dataset_config in datasets.items():
            if not isinstance(dataset_config, dict):
                continue
            
            owner_user, owner_group = self._extract_owner(dataset_config)
            self.register_dataset(dataset_path, owner_user, owner_group)
            
            consumers = (
                dataset_config.get('_consumers')
                or dataset_config.get('consumers')
                or []
            )
            
            if not isinstance(consumers, list):
                logger.warning(
                    "Invalid consumers format for %s (expected list)", dataset_path
                )
                continue
            
            for idx, consumer in enumerate(consumers):
                if not isinstance(consumer, dict):
                    logger.warning(
                        "Skipping consumer %s[%d]: expected dict, got %s",
                        dataset_path,
                        idx,
                        type(consumer).__name__,
                    )
                    continue
                
                consumer_type = self._consumer_type_from_config(
                    consumer.get('type')
                )
                access_level = self._access_level_from_config(
                    consumer.get('access')
                )
                name = consumer.get('name')
                
                if not consumer_type or not access_level or not name:
                    logger.warning(
                        "Skipping consumer %s[%d]: missing or invalid fields",
                        dataset_path,
                        idx,
                    )
                    continue
                
                try:
                    self.add_consumer(
                        dataset_path,
                        consumer_type,
                        name,
                        access_level,
                    )
                except PermissionConflict as exc:
                    logger.warning(
                        "Permission conflict for %s: %s (consumer=%s)",
                        dataset_path,
                        exc,
                        name,
                    )

    def _extract_owner(self, dataset_config: Dict[str, Any]) -> Tuple[str, str]:
        """Determine owner user/group from dataset permissions."""
        permissions = dataset_config.get('permissions') or {}
        
        # Support uid/gid keys as well as user/group for future schemas
        owner_user = permissions.get('user', permissions.get('uid', 'root'))
        owner_group = permissions.get('group', permissions.get('gid', 'root'))
        
        # Also support nested owner definitions if present
        if isinstance(permissions.get('owner'), dict):
            owner = permissions['owner']
            owner_user = owner.get('user', owner_user)
            owner_group = owner.get('group', owner_group)
        
        return str(owner_user), str(owner_group)

    def _consumer_type_from_config(self, raw_type: Optional[str]) -> Optional[ConsumerType]:
        """Convert config consumer type into enum."""
        if not raw_type:
            return None
        
        normalized = raw_type.strip().lower()
        mapping = {
            'container': ConsumerType.CONTAINER,
            'smb': ConsumerType.SHARE_SMB,
            'share': ConsumerType.SHARE_SMB,
            'nfs': ConsumerType.SHARE_NFS,
            'user': ConsumerType.USER,
            'group': ConsumerType.GROUP,
        }
        return mapping.get(normalized)

    def _access_level_from_config(self, raw_access: Optional[str]) -> Optional[AccessLevel]:
        """Convert config access level string into enum."""
        if not raw_access:
            return None
        
        normalized = raw_access.strip().lower()
        mapping = {
            'read': AccessLevel.READ,
            'write': AccessLevel.WRITE,
        }
        return mapping.get(normalized)

    def _find_existing_consumer(
        self,
        perm_set: PermissionSet,
        consumer_type: ConsumerType,
        name: str,
    ) -> Optional[Consumer]:
        """Return existing consumer entry if present."""
        for consumer in perm_set.consumers:
            if consumer.name == name and consumer.type == consumer_type:
                return consumer
        return None
