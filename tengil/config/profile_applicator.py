"""ZFS profile application for datasets.

Applies predefined ZFS property profiles to datasets and handles nested
dataset expansion for hierarchical paths.
"""
from typing import Dict, Any

from tengil.config.profiles import PROFILES


class ProfileApplicator:
    """Applies ZFS profiles and expands nested dataset paths.
    
    Handles:
    - Profile application (media, photos, backups, etc.)
    - Nested dataset expansion (media/movies/4k → media, media/movies, media/movies/4k)
    - Auto-parent generation with inherited profiles
    """

    def expand_nested_datasets(self, datasets: Dict[str, Any]) -> Dict[str, Any]:
        """Expand nested dataset notation into explicit parent datasets.
        
        Converts: media/movies/4k → media, media/movies, media/movies/4k
        
        Auto-generates parent datasets with:
        - Inherited profile from first child
        - Minimal ZFS configuration
        - _auto_parent marker
        
        Args:
            datasets: Dictionary of dataset configurations
            
        Returns:
            Expanded dataset dictionary with all parents explicit
        """
        expanded = {}

        # Collect all dataset paths (including parents)
        all_paths = set(datasets.keys())

        # For each dataset with slashes, ensure parents exist
        for name in list(all_paths):
            parts = name.split('/')

            # Add all parent paths
            for i in range(1, len(parts)):
                parent_path = '/'.join(parts[:i])
                all_paths.add(parent_path)

        # Sort to ensure parents come before children
        sorted_paths = sorted(all_paths, key=lambda x: (x.count('/'), x))

        # Build expanded config
        for path in sorted_paths:
            if path in datasets:
                # User-defined dataset - use their config
                expanded[path] = datasets[path]
            else:
                # Auto-generated parent dataset - minimal config
                # Inherit profile from first child if possible
                child_profile = None
                for dataset_name, dataset_config in datasets.items():
                    if dataset_name.startswith(path + '/'):
                        child_profile = dataset_config.get('profile')
                        break

                expanded[path] = {
                    '_auto_parent': True,  # Mark as auto-generated
                    'profile': child_profile or 'media',  # Default to media profile
                    'zfs': {}
                }

        return expanded

    def apply_profile(self, dataset: Dict[str, Any]) -> None:
        """Apply ZFS profile defaults to dataset configuration.
        
        Merges profile properties into dataset's ZFS settings.
        Dataset-specific ZFS settings take precedence over profile defaults.
        
        Available profiles: media, photos, documents, backups, vm-storage, etc.
        
        Args:
            dataset: Dataset configuration dictionary (modified in place)
        """
        profile_name = dataset.get('profile')
        if not profile_name:
            return

        if profile_name in PROFILES:
            # Merge profile defaults with dataset config
            profile_defaults = PROFILES[profile_name].copy()

            # Dataset-specific ZFS settings override profile
            if 'zfs' not in dataset:
                dataset['zfs'] = {}

            for key, value in profile_defaults.items():
                if key not in dataset['zfs']:
                    dataset['zfs'][key] = value
