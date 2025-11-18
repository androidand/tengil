"""Core scaffolding functionality for homelab repositories."""

import os
from pathlib import Path
from typing import Dict, List, Optional

from tengil.core.logger import get_logger

logger = get_logger(__name__)


class ScaffoldManager:
    """Manages homelab repository scaffolding."""
    
    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or Path(__file__).parent / "templates"
    
    def scaffold_homelab(
        self,
        name: str,
        server_ip: str,
        template: str = "basic",
        output_dir: Optional[Path] = None,
        apps: Optional[List[str]] = None
    ) -> Path:
        """Scaffold a complete homelab repository.
        
        Args:
            name: Homelab name (e.g., "andreas-homelab")
            server_ip: Proxmox server IP (e.g., "192.168.1.42")
            template: Template type (basic, media-server, dev-workstation)
            output_dir: Output directory (defaults to current dir)
            apps: List of apps to scaffold (e.g., ["nodejs-api", "static-site"])
        
        Returns:
            Path to created repository
        """
        output_dir = output_dir or Path.cwd()
        repo_path = output_dir / name
        
        logger.info(f"✨ Creating homelab repository: {name}")
        
        # Create directory structure
        self._create_directory_structure(repo_path)
        
        # Generate main config
        self._generate_tengil_config(repo_path, template, apps or [])
        
        # Generate deployment scripts
        self._generate_deployment_scripts(repo_path, server_ip)
        
        # Generate security files
        self._generate_security_files(repo_path)
        
        # Generate documentation
        self._generate_documentation(repo_path, name, server_ip)
        
        # Scaffold apps if requested
        if apps:
            for app_type in apps:
                self._scaffold_app(repo_path, app_type, f"my-{app_type}")
        
        logger.info(f"📁 Generated directory structure")
        logger.info(f"🔧 Created deployment scripts") 
        logger.info(f"📝 Generated documentation")
        logger.info(f"🔐 Configured security settings")
        
        return repo_path
    
    def _create_directory_structure(self, repo_path: Path) -> None:
        """Create the basic directory structure."""
        directories = [
            "apps",
            "configs", 
            "scripts",
            "secrets"
        ]
        
        repo_path.mkdir(exist_ok=True)
        for directory in directories:
            (repo_path / directory).mkdir(exist_ok=True)
    
    def _generate_tengil_config(self, repo_path: Path, template: str, apps: List[str]) -> None:
        """Generate main tengil.yml configuration."""
        # This will use the template engine once implemented
        basic_config = """# Homelab Infrastructure Configuration
pools:
  tank:
    type: zfs
    datasets:
      # Personal webservices
      webservices:
        profile: appdata
        shares:
          smb:
            name: "WebServices"
      
      # Static websites  
      websites:
        profile: media
        shares:
          smb:
            name: "Websites"
      
      # Personal documents
      documents:
        profile: documents
        shares:
          smb:
            name: "Documents"
            valid_users: "@family"
"""
        
        (repo_path / "tengil.yml").write_text(basic_config)
    
    def _generate_deployment_scripts(self, repo_path: Path, server_ip: str) -> None:
        """Generate deployment automation scripts."""
        deploy_script = f"""#!/bin/bash
set -e

SERVER="root@{server_ip}"
REMOTE_DIR="/root/homelab"

echo "🚀 Deploying homelab config to Proxmox..."

# Sync config files (excluding secrets)
rsync -av --exclude='.git' --exclude='.env' --exclude='secrets/' \\
  ./ $SERVER:$REMOTE_DIR/

# Deploy infrastructure
ssh $SERVER "cd $REMOTE_DIR && tg diff && tg apply"

echo "✅ Deployment complete!"
"""
        
        deploy_path = repo_path / "scripts" / "deploy.sh"
        deploy_path.write_text(deploy_script)
        deploy_path.chmod(0o755)
    
    def _generate_security_files(self, repo_path: Path) -> None:
        """Generate security configuration files."""
        gitignore = """.env
*.key
*.pem
secrets/
.tengil.state.json
__pycache__/
*.pyc
.DS_Store
"""
        
        env_example = """# Database credentials
DB_PASSWORD=your_secure_password_here
API_KEY=your_api_key_here

# App-specific secrets  
BLOG_ADMIN_PASSWORD=admin_password
"""
        
        (repo_path / ".gitignore").write_text(gitignore)
        (repo_path / ".env.example").write_text(env_example)
    
    def _generate_documentation(self, repo_path: Path, name: str, server_ip: str) -> None:
        """Generate README and documentation."""
        readme = f"""# {name}

Personal homelab infrastructure managed with [Tengil](https://github.com/androidand/tengil).

## Quick Start

```bash
# Deploy infrastructure
./scripts/deploy.sh

# Check status
ssh root@{server_ip} "cd /root/homelab && tg status"
```

## Repository Structure

- `tengil.yml` - Infrastructure configuration
- `apps/` - Application configurations
- `scripts/` - Deployment automation
- `configs/` - Service configurations

## Workflow

1. Edit configs locally on Mac
2. Test changes: `tg diff`
3. Deploy: `./scripts/deploy.sh`
4. Commit: `git add -A && git commit -m "Description"`

## Security

- Secrets are in `.env` (not committed)
- Use `.env.example` as template  
- SSH keys required for deployment
- Never commit real passwords or API keys
- Review `.gitignore` before first commit

## Apps

Add new applications:
```bash
tg scaffold app nodejs-api --name my-new-service
```
"""
        
        (repo_path / "README.md").write_text(readme)
    
    def _scaffold_app(self, repo_path: Path, app_type: str, app_name: str) -> None:
        """Scaffold a specific application."""
        if app_type == "nodejs-api":
            app_path = repo_path / "apps" / app_name
            app_path.mkdir(exist_ok=True)
            self._scaffold_nodejs_app(app_path, app_name)
        elif app_type == "static-site":
            app_path = repo_path / "apps" / app_name
            app_path.mkdir(exist_ok=True)
            self._scaffold_static_site(app_path, app_name)
        else:
            # Unknown app type - skip scaffolding but don't fail
            logger.warning(f"Unknown app type '{app_type}' - skipping scaffolding")
    
    def _scaffold_nodejs_app(self, app_path: Path, app_name: str) -> None:
        """Scaffold a Node.js API application."""
        package_json = {
            "name": app_name,
            "version": "1.0.0",
            "main": "app.js",
            "scripts": {
                "start": "node app.js",
                "dev": "nodemon app.js"
            },
            "dependencies": {
                "express": "^4.18.0"
            }
        }
        
        app_js = """const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.json({ message: 'Hello from Tengil!' });
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
"""
        
        import json
        (app_path / "package.json").write_text(json.dumps(package_json, indent=2))
        (app_path / "app.js").write_text(app_js)
    
    def _scaffold_static_site(self, app_path: Path, app_name: str) -> None:
        """Scaffold a static website."""
        index_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{app_name}</title>
</head>
<body>
    <h1>Welcome to {app_name}</h1>
    <p>Deployed with Tengil!</p>
</body>
</html>
"""
        
        (app_path / "index.html").write_text(index_html)