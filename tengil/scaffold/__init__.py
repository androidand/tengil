"""Homelab repository scaffolding system.

Transforms Tengil from config generator to complete homelab lifecycle tool.
"""

from .core import ScaffoldManager
from .deploy import DeploymentScriptGenerator
from .templates import TemplateEngine

__all__ = [
    "ScaffoldManager",
    "TemplateEngine", 
    "DeploymentScriptGenerator",
]