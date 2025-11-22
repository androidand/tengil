"""Container configuration parsing and validation.

Handles container mount specifications, format migrations, and validation
for container definitions in dataset configurations.
"""
import warnings
from typing import Any, Dict, List, Optional, Set, Tuple

from tengil.core.smart_permissions import _match_known_container
from tengil.models.config import ConfigValidationError


class ContainerParser:
    """Parses and validates container configurations.
    
    Handles:
    - Deprecated format migrations (id→name, path→mount)
    - Multiple container specification formats (string, dict)
    - Container resource specifications
    - Global container defaults merging
    - Smart permission inference helpers
    """

    def __init__(self, raw_config: Optional[Dict[str, Any]] = None):
        """Initialize container parser.
        
        Args:
            raw_config: Full raw configuration (for global container defaults)
        """
        self.raw_config = raw_config or {}

    def fix_container_format(self, containers: List, dataset_path: str) -> List:
        """Fix deprecated container mount formats.

        Handles migrations:
        - 'id' (VMID) → warn (can't auto-fix)
        - 'path' → 'mount'

        Args:
            containers: List of container configurations
            dataset_path: Dataset path for error messages

        Returns:
            Fixed container list
        """
        if not containers:
            return containers

        fixed = []
        for _idx, container in enumerate(containers):
            if isinstance(container, str):
                # String format is fine (e.g., 'jellyfin:/media')
                fixed.append(container)
                continue

            if not isinstance(container, dict):
                raise ConfigValidationError(
                    f"Invalid container format in '{dataset_path}': {container}\n"
                    f"  Must be either dict or string.\n"
                    f"  Examples:\n"
                    f"    - name: jellyfin\n"
                    f"      mount: /media\n"
                    f"    - 'jellyfin:/media'"
                )

            # Check for deprecated 'id' field (Proxmox VMID)
            if 'id' in container:
                warnings.warn(
                    f"Deprecated container format in '{dataset_path}':\n"
                    f"  Use 'name:' (container hostname) instead of 'id:' (VMID)\n"
                    f"  \n"
                    f"  Current (deprecated):\n"
                    f"    - id: {container['id']}\n"
                    f"      mount: {container.get('mount', '...')}\n"
                    f"  \n"
                    f"  Correct format:\n"
                    f"    - name: jellyfin  # Container hostname from Proxmox\n"
                    f"      mount: /media\n"
                    f"  \n"
                    f"  To find container name: pct config {container['id']} | grep hostname\n"
                    f"  This format will be removed in v1.0",
                    DeprecationWarning,
                    stacklevel=5  # Adjust for call stack
                )

            # Check for deprecated 'path' field (should be 'mount')
            if 'path' in container:
                warnings.warn(
                    f"Deprecated container format in '{dataset_path}':\n"
                    f"  Use 'mount:' instead of 'path:'\n"
                    f"  \n"
                    f"  Current (deprecated):\n"
                    f"    - name: {container.get('name', '...')}\n"
                    f"      path: {container['path']}\n"
                    f"  \n"
                    f"  Correct format:\n"
                    f"    - name: {container.get('name', '...')}\n"
                    f"      mount: {container['path']}\n"
                    f"  \n"
                    f"  This format will be removed in v1.0",
                    DeprecationWarning,
                    stacklevel=5  # Adjust for call stack
                )
                # Auto-fix: rename 'path' to 'mount'
                container['mount'] = container.pop('path')

            fixed.append(container)

        return fixed

    def parse_container_mounts(self, containers: List, dataset_path: str) -> List:
        """Parse and validate container configurations.
        
        Validates container specs but preserves original format for backward compatibility.
        
        Supports multiple formats:
        - Simple string: "jellyfin:/media" (kept as-is)
        - Dict with name: {name: jellyfin, mount: /media}
        - Dict with vmid: {vmid: 100, mount: /media}
        - Phase 2+: Full specs with auto_create, template, resources
        
        Args:
            containers: List of container configurations
            dataset_path: Dataset path for error messages
            
        Returns:
            List of validated containers (format preserved)
        """
        if not containers:
            return []
        
        parsed = []
        for container in containers:
            # String format: "name:/mount" or "name:/mount:ro"
            if isinstance(container, str):
                parts = container.split(':')
                if len(parts) < 2:
                    raise ConfigValidationError(
                        f"Invalid container string format in '{dataset_path}': {container}\n"
                        f"  Expected: 'name:/mount' or 'name:/mount:ro'"
                    )
                # Validate and keep string format
                parsed.append(container)
                continue

            # Dict format
            if not isinstance(container, dict):
                raise ConfigValidationError(
                    f"Invalid container type in '{dataset_path}': {type(container)}"
                )

            # Keep original dict mostly as-is, just validate and merge defaults
            container_data = container.copy()

            # Handle deprecated 'id' field (already warned in fix_container_format)
            # Map 'id' to 'vmid' for internal consistency
            if 'id' in container_data and 'vmid' not in container_data:
                container_data['vmid'] = container_data['id']

            # Validate mount point
            if not container_data.get('mount'):
                raise ConfigValidationError(
                    f"Container in '{dataset_path}' missing required 'mount' field"
                )

            # Validate pool field
            if 'pool' in container_data and container_data['pool'] is not None:
                pool_value = container_data['pool']
                if not isinstance(pool_value, str):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid pool value: {pool_value}\n"
                        f"  'pool' must be a string matching an existing Proxmox resource pool."
                    )
                container_data['pool'] = pool_value.strip()

            # Validate privileged field
            if 'privileged' in container_data:
                privileged_value = container_data['privileged']
                if not isinstance(privileged_value, bool):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid privileged flag: {privileged_value}\n"
                        f"  'privileged' must be true or false."
                    )
            
            # Validate description field
            if 'description' in container_data and container_data['description'] is not None:
                if not isinstance(container_data['description'], str):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid description (must be string)."
                    )
                container_data['description'] = container_data['description'].strip()
            
            # Validate tags field
            if 'tags' in container_data and container_data['tags'] is not None:
                tags_value = container_data['tags']
                if isinstance(tags_value, str):
                    tags_value = [tag.strip() for tag in tags_value.split(',') if tag.strip()]
                if not isinstance(tags_value, list) or not all(isinstance(tag, str) for tag in tags_value):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid 'tags'. Use list of strings."
                    )
                container_data['tags'] = [tag.strip() for tag in tags_value if tag.strip()]

            # Validate startup_order field
            if 'startup_order' in container_data and container_data['startup_order'] is not None:
                order_val = container_data['startup_order']
                try:
                    order_int = int(order_val)
                except (TypeError, ValueError):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid startup_order '{order_val}'. Must be integer."
                    )
                if order_int < 0:
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has negative startup_order '{order_int}'."
                    )
                container_data['startup_order'] = order_int

            # Validate startup_delay field
            if 'startup_delay' in container_data and container_data['startup_delay'] is not None:
                delay_val = container_data['startup_delay']
                try:
                    delay_int = int(delay_val)
                except (TypeError, ValueError):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid startup_delay '{delay_val}'. Must be integer seconds."
                    )
                if delay_int < 0:
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has negative startup_delay '{delay_int}'."
                    )
                container_data['startup_delay'] = delay_int

            # Validate startup field
            if 'startup' in container_data and container_data['startup'] is not None:
                if not isinstance(container_data['startup'], str):
                    raise ConfigValidationError(
                        f"Container in '{dataset_path}' has invalid startup string. Must be text."
                    )
                container_data['startup'] = container_data['startup'].strip()

            container_data = self._merge_container_defaults(container_data)
            container_data = self._normalize_oci_spec(container_data, dataset_path)

            parsed.append(container_data)

        return parsed

    def _merge_container_defaults(self, container: Dict) -> Dict:
        """Merge top-level container defaults into dataset container specs.
        
        Args:
            container: Container configuration
            
        Returns:
            Merged container configuration with defaults applied
        """
        container_name = container.get('name')
        if not container_name:
            return container

        global_containers = {}
        if isinstance(self.raw_config, dict):
            global_containers = self.raw_config.get('containers', {})

        if not isinstance(global_containers, dict):
            return container

        defaults = global_containers.get(container_name)
        if not isinstance(defaults, dict):
            return container

        merged = defaults.copy()
        merged.update(container)

        resources: Dict[str, Any] = {}

        def apply_resource(source: Dict[str, Any]):
            if not isinstance(source, dict):
                return
            if 'resources' in source and isinstance(source['resources'], dict):
                resources.update(source['resources'])
            if 'memory' in source:
                resources['memory'] = source['memory']
            if 'cores' in source:
                resources['cores'] = source['cores']
            if 'swap' in source:
                resources['swap'] = source['swap']
            if 'disk' in source:
                resources['disk'] = source['disk']
            if 'disk_size' in source:
                resources['disk'] = self._format_disk_size(source['disk_size'])

        apply_resource(defaults)
        apply_resource(container)

        if resources:
            merged['resources'] = resources

        # Auto-enable auto_create if template is specified
        if 'auto_create' not in merged:
            if merged.get('template'):
                merged['auto_create'] = True

        return merged

    def _normalize_oci_spec(self, container: Dict[str, Any], dataset_path: str) -> Dict[str, Any]:
        """Ensure OCI containers have an 'oci' section, supporting top-level image field."""
        if container.get('type') != 'oci':
            return container

        # If already structured, just ensure image exists
        if 'oci' in container:
            oci_spec = container.get('oci') or {}
            if not isinstance(oci_spec, dict):
                raise ConfigValidationError(
                    f"Container in '{dataset_path}' has invalid 'oci' section (must be a mapping)."
                )
            if not oci_spec.get('image') and container.get('image'):
                image, tag = self._split_image_and_tag(container['image'])
                oci_spec['image'] = image
                oci_spec.setdefault('tag', tag)
                if container.get('registry') and 'registry' not in oci_spec:
                    oci_spec['registry'] = container['registry']
                container['oci'] = oci_spec
            elif not oci_spec.get('image'):
                raise ConfigValidationError(
                    f"Container in '{dataset_path}' type 'oci' requires 'oci.image' or top-level 'image'."
                )
            return container

        image_value = container.get('image')
        if not image_value:
            raise ConfigValidationError(
                f"Container in '{dataset_path}' type 'oci' requires 'image' (or oci.image) field."
            )

        image, tag = self._split_image_and_tag(image_value)
        registry = container.get('registry')
        oci_spec = {'image': image, 'tag': tag}
        if registry:
            oci_spec['registry'] = registry
        container['oci'] = oci_spec
        return container

    @staticmethod
    def _split_image_and_tag(image_value: str) -> Tuple[str, str]:
        """Split image into image + tag, handling registry prefixes."""
        if ":" in image_value and image_value.rfind(":") > image_value.rfind("/"):
            image, tag = image_value.rsplit(":", 1)
        else:
            image, tag = image_value, "latest"
        return image, tag

    @staticmethod
    def capture_explicit_readonly(containers: List[Any]) -> Set[int]:
        """Capture indices of containers with explicit readonly flags.
        
        Used to avoid stripping explicitly-set readonly flags during
        smart permission inference.
        
        Args:
            containers: List of container configurations
            
        Returns:
            Set of indices with explicit readonly flags
        """
        indices: Set[int] = set()
        for idx, container in enumerate(containers):
            if isinstance(container, dict) and 'readonly' in container:
                indices.add(idx)
        return indices

    @staticmethod
    def strip_inferred_readonly(
        containers: List[Any],
        explicit_indices: Set[int],
        profile: Optional[str]
    ) -> None:
        """Strip inferred readonly flags from known containers.
        
        Smart permission system infers readonly flags for media/photos profiles.
        This strips those inferred flags for known containers (like Jellyfin)
        where the readonly is redundant with smart defaults.
        
        Args:
            containers: List of container configurations (modified in place)
            explicit_indices: Indices with explicit readonly (don't strip these)
            profile: Dataset profile name
        """
        readonly_profiles = {"media", "photos", "documents", "backups"}
        profile_name = (profile or "").lower()

        for idx, container in enumerate(containers):
            if idx in explicit_indices:
                continue
            if isinstance(container, dict):
                if 'readonly' not in container:
                    continue

                if not container['readonly']:
                    continue

                if profile_name not in readonly_profiles:
                    continue

                match = _match_known_container(container.get('name', '') or '')
                if match and match[2]:  # Exact known match
                    container.pop('readonly', None)

    @staticmethod
    def _format_disk_size(value: Any) -> str:
        """Normalize disk size to Proxmox-compatible string.
        
        Args:
            value: Disk size (integer GB or string)
            
        Returns:
            Formatted disk size string (e.g., "32G")
        """
        if isinstance(value, (int, float)):
            return f"{int(value)}G"
        return str(value)
