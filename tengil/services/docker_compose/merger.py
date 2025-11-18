"""
Opinion merger for Docker Compose requirements + Tengil storage hints.

Takes extracted compose requirements and merges them with Tengil's
storage optimization opinions to generate tengil.yml configuration.
"""

from typing import Dict, List, Optional

from .analyzer import ComposeRequirements


class OpinionMerger:
    """
    Merges Docker Compose requirements with Tengil storage opinions.
    
    Input:
    - ComposeRequirements (from compose file)
    - Package storage_hints (Tengil opinions)
    
    Output:
    - tengil.yml configuration (datasets with consumers)
    """
    
    def merge(self, requirements: ComposeRequirements, package: dict) -> dict:
        """
        Generate tengil.yml from compose requirements + storage opinions.
        
        Args:
            requirements: Extracted from compose file
            package: Package metadata with storage_hints, share_recommendations, etc.
            
        Returns:
            Dictionary ready to write as tengil.yml
        """
        config = {
            'pools': {
                'tank': {
                    'type': 'zfs',
                    'datasets': {}
                }
            },
            'containers': {},
            '_metadata': {
                'generated_from': 'docker_compose',
                'compose_services': requirements.services
            }
        }
        
        # Process each volume from compose
        datasets = config['pools']['tank']['datasets']
        
        for volume in requirements.volumes:
            dataset_name = self._path_to_dataset_name(volume.host)
            
            # Get Tengil's storage hints for this volume
            hints = package.get('storage_hints', {}).get(volume.host, {})
            share_recs = package.get('share_recommendations', {}).get(volume.host, {})
            
            # Create or update dataset
            if dataset_name not in datasets:
                datasets[dataset_name] = self._create_dataset(
                    volume.host, hints, share_recs
                )
            
            # Add container consumer
            self._add_container_consumer(
                datasets[dataset_name],
                volume.service,
                volume.host,
                volume.readonly
            )
        
        # Add container configuration if provided
        if 'container' in package:
            container_config = package['container'].copy()
            # Use first service name as container name (convention)
            container_name = requirements.services[0] if requirements.services else 'app'
            config['containers'][container_name] = container_config
        
        return config
    
    def _path_to_dataset_name(self, path: str) -> str:
        """
        Convert host path to dataset name.
        
        Examples:
            /roms -> roms
            /romm/assets -> romm-assets
        """
        # Remove leading slash
        name = path.lstrip('/')
        # Replace remaining slashes with hyphens
        name = name.replace('/', '-')
        return name
    
    def _create_dataset(self, host_path: str, hints: dict, share_recs: dict) -> dict:
        """Create dataset configuration from hints."""
        dataset = {
            'consumers': []
        }
        
        # Apply storage hints (Tengil's opinions)
        if 'profile' in hints:
            dataset['profile'] = hints['profile']
        
        # Add metadata (for documentation/debugging)
        if hints.get('why'):
            dataset['_why'] = hints['why']
        if hints.get('size_estimate'):
            dataset['_size_estimate'] = hints['size_estimate']
        
        # Add SMB share consumer if recommended
        if share_recs.get('smb'):
            self._add_smb_consumer(
                dataset,
                share_recs.get('smb_name', host_path.lstrip('/').upper()),
                host_path,
                share_recs.get('read_only', False)
            )
        
        # Add NFS share consumer if recommended
        if share_recs.get('nfs'):
            self._add_nfs_consumer(
                dataset,
                host_path,
                share_recs.get('read_only', False)
            )
        
        return dataset
    
    def _add_container_consumer(self, dataset: dict, container_name: str, 
                                 mount_path: str, readonly: bool):
        """Add container consumer to dataset."""
        consumer = {
            'type': 'container',
            'name': container_name,
            'access': 'read' if readonly else 'write',
            'mount': mount_path
        }
        
        # Check if already exists (avoid duplicates)
        for existing in dataset['consumers']:
            if (existing.get('type') == 'container' and 
                existing.get('name') == container_name and
                existing.get('mount') == mount_path):
                return
        
        dataset['consumers'].append(consumer)
    
    def _add_smb_consumer(self, dataset: dict, share_name: str, 
                          mount_path: str, readonly: bool):
        """Add SMB share consumer to dataset."""
        consumer = {
            'type': 'smb',
            'name': share_name,
            'access': 'read' if readonly else 'write'
        }
        dataset['consumers'].append(consumer)
    
    def _add_nfs_consumer(self, dataset: dict, mount_path: str, readonly: bool):
        """Add NFS share consumer to dataset."""
        consumer = {
            'type': 'nfs',
            'name': mount_path.lstrip('/'),
            'access': 'read' if readonly else 'write'
        }
        dataset['consumers'].append(consumer)
    
    def merge_interactive(self, requirements: ComposeRequirements, 
                         package: Optional[dict] = None) -> dict:
        """
        Interactive merge - prompt user for storage hints if not in package.
        
        This would be used for: tg init --from-compose my-app.yml
        where we don't have pre-defined storage hints.
        """
        if package is None:
            package = {}
        
        # TODO: Implement interactive prompts
        # For each volume:
        #   - Ask user: What type of data? (media/docs/database/dev/other)
        #   - Suggest profile based on answer
        #   - Ask: Estimate size?
        #   - Ask: Need SMB share?
        #
        # For now, just use defaults
        if 'storage_hints' not in package:
            package['storage_hints'] = {}
            for volume in requirements.volumes:
                if volume.host not in package['storage_hints']:
                    package['storage_hints'][volume.host] = {
                        'profile': 'default',
                        'why': 'User to customize'
                    }
        
        return self.merge(requirements, package)
