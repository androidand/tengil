"""
Docker Compose integration services.

Provides tools for analyzing Docker Compose files and merging with Tengil storage opinions.
"""

from .analyzer import ComposeAnalyzer, ComposeRequirements, VolumeMount
from .merger import OpinionMerger
from .resolver import ComposeResolver, ComposeSource

__all__ = [
    "ComposeAnalyzer",
    "ComposeRequirements",
    "VolumeMount",
    "OpinionMerger",
    "ComposeResolver",
    "ComposeSource",
]
