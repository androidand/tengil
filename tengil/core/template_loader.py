"""Template and dataset loading for tengil configuration."""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class TemplateLoader:
    """Loads and merges templates and dataset definitions."""

    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize template loader.

        Args:
            templates_dir: Path to templates directory. Defaults to tengil/templates/
        """
        if templates_dir is None:
            # Loader is in tengil/core/, templates are in tengil/templates/
            templates_dir = Path(__file__).parent.parent / "templates"
        self.templates_dir = templates_dir
        self.datasets_dir = templates_dir / "datasets"
    
    def load_template(self, template_name: str) -> dict:
        """Load a template YAML file.
        
        Args:
            template_name: Name of template (without .yml extension)
            
        Returns:
            Template configuration dictionary
            
        Raises:
            FileNotFoundError: If template doesn't exist
        """
        template_path = self.templates_dir / f"{template_name}.yml"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template '{template_name}' not found at {template_path}"
            )
        
        with open(template_path) as f:
            return yaml.safe_load(f)
    
    def load_dataset(self, dataset_name: str) -> dict:
        """Load an individual dataset YAML file.
        
        Returns just the dataset definition without description.
        
        Args:
            dataset_name: Name of dataset (without .yml extension)
            
        Returns:
            Dataset configuration dictionary
            
        Raises:
            FileNotFoundError: If dataset doesn't exist
        """
        dataset_path = self.datasets_dir / f"{dataset_name}.yml"
        if not dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset '{dataset_name}' not found at {dataset_path}"
            )
        
        with open(dataset_path) as f:
            data = yaml.safe_load(f)
            # Remove description field and return the dataset definition
            if 'description' in data:
                del data['description']
            return data
    
    def get_dataset_info(self, dataset_name: str) -> Tuple[str, dict]:
        """Get dataset description and definition.
        
        Args:
            dataset_name: Name of dataset
            
        Returns:
            Tuple of (description, dataset_config)
        """
        dataset_path = self.datasets_dir / f"{dataset_name}.yml"
        if not dataset_path.exists():
            return ("No description", {})
        
        with open(dataset_path) as f:
            data = yaml.safe_load(f)
            description = data.pop('description', 'No description')
            return (description, data)
    
    def get_template_info(self, template_name: str) -> str:
        """Get template description.
        
        Args:
            template_name: Name of template
            
        Returns:
            Template description string
        """
        template_path = self.templates_dir / f"{template_name}.yml"
        if not template_path.exists():
            return "No description"
        
        with open(template_path) as f:
            data = yaml.safe_load(f)
            return data.get('description', 'No description')
    
    def list_templates(self) -> List[str]:
        """List all available template files.
        
        Returns:
            List of template names (without .yml extension)
        """
        if not self.templates_dir.exists():
            return []
        return [f.stem for f in self.templates_dir.glob("*.yml")]
    
    def list_datasets(self) -> List[str]:
        """List all available dataset files.
        
        Returns:
            List of dataset names (without .yml extension)
        """
        if not self.datasets_dir.exists():
            return []
        return [f.stem for f in self.datasets_dir.glob("*.yml")]
    
    def merge_configs(self, configs: List[dict]) -> dict:
        """Merge multiple configuration dictionaries.
        
        Resolves dataset references by loading actual definitions.
        
        Args:
            configs: List of config dictionaries to merge
            
        Returns:
            Merged configuration dictionary
        """
        pool_name = "tank"
        pool_type = "zfs"
        datasets_accum: Dict[str, dict] = {}
        
        for config in configs:
            if "pool" in config:
                pool_name = config["pool"]
            if "pool_type" in config:
                pool_type = config["pool_type"]
            if "pools" in config and isinstance(config["pools"], dict):
                # Merge already structured pools
                for pool, pool_data in config["pools"].items():
                    datasets = pool_data.get("datasets", {})
                    datasets_accum.update(datasets)
                continue
                
            if "datasets" in config:
                datasets = config["datasets"]
                
                # Handle list of dataset references
                if isinstance(datasets, list):
                    for dataset_ref in datasets:
                        # Load the actual dataset definition
                        dataset_data = self.load_dataset(dataset_ref)
                        datasets_accum.update(dataset_data)
                # Handle dict of dataset definitions (direct definitions)
                elif isinstance(datasets, dict):
                    datasets_accum.update(datasets)
        
        return {
            "pools": {
                pool_name: {
                    "type": pool_type,
                    "datasets": datasets_accum
                }
            }
        }
    
    def substitute_pool(self, config: dict, pool: str) -> dict:
        """Replace ${pool} variable in configuration.
        
        Args:
            config: Configuration dictionary
            pool: Pool name to substitute
            
        Returns:
            Configuration with substitutions applied
        """
        config_str = yaml.dump(config)
        config_str = config_str.replace("${pool}", pool)
        return yaml.safe_load(config_str)
