"""Homelab repository scaffolding system.

Transforms Tengil from config generator to complete homelab lifecycle tool.
"""

from .core import ScaffoldManager
from .templates import TemplateEngine
from .deploy import DeploymentScriptGenerator

__all__ = [
    "ScaffoldManager",
    "TemplateEngine", 
    "DeploymentScriptGenerator",
]