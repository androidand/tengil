"""Template engine for homelab scaffolding."""

from pathlib import Path
from typing import Any, Dict


class TemplateEngine:
    """Handles template rendering for scaffolding."""
    
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a template with given context."""
        # Placeholder for Jinja2 integration
        template_path = self.template_dir / f"{template_name}.j2"
        if template_path.exists():
            content = template_path.read_text()
            # Simple string replacement for now
            for key, value in context.items():
                content = content.replace(f"{{{{{key}}}}}", str(value))
            return content
        return ""