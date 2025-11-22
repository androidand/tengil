"""Template loading and management.

DEPRECATED: TemplateLoader has moved to tengil.core.template_loader
This module provides backwards compatibility.
"""
import warnings

from tengil.core.template_loader import TemplateLoader

warnings.warn(
    "Importing from tengil.templates is deprecated. "
    "Use 'from tengil.core.template_loader import TemplateLoader' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['TemplateLoader']
