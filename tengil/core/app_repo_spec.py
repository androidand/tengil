"""Utilities for loading app repository specifications."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


@dataclass
class AppRepoSpec:
    """Specification describing how to sync an app repository."""

    name: Optional[str]
    target: str
    repo: str
    branch: str = "main"
    path: Optional[str] = None
    manifest_root: Optional[str] = None
    manifest_glob: Optional[str] = None
    manifest_depth: Optional[int] = None

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        base_path: Optional[Path] = None,
    ) -> "AppRepoSpec":
        """Construct spec from a dictionary definition.

        Supports either inline definitions or references to an external spec file
        via ``spec``/``select`` keys. Any inline values override referenced spec
        fields.
        """

        if not isinstance(data, dict):
            raise AppRepoSpecError("App repo definition must be a mapping")

        if 'spec' in data and data['spec']:
            referenced = _load_from_spec_reference(data, base_path=base_path)
            return referenced

        name = _coerce_optional_str(data.get('name'))
        target = _coerce_required_str(data.get('target'), "target")
        repo = _coerce_required_str(data.get('repo'), "repo")
        branch = _coerce_optional_str(data.get('branch')) or "main"
        path_value = _coerce_optional_str(data.get('path'))

        manifests = data.get('manifests') if isinstance(data.get('manifests'), dict) else {}
        manifest_root = _manifest_root_from(manifests, path_value)
        manifest_glob = _coerce_optional_str(manifests.get('glob'))
        manifest_depth = _coerce_optional_int(manifests.get('depth'))

        return cls(
            name=name,
            target=target,
            repo=repo,
            branch=branch,
            path=path_value,
            manifest_root=manifest_root,
            manifest_glob=manifest_glob,
            manifest_depth=manifest_depth,
        )


class AppRepoSpecError(Exception):
    """Raised when an app repo specification cannot be loaded."""


def _normalize_entries(data: Any) -> List[Dict[str, Any]]:
    """Return a list of spec entries from raw YAML data."""
    if not data:
        return []

    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]

    if isinstance(data, dict):
        if isinstance(data.get('repos'), list):
            return [entry for entry in data['repos'] if isinstance(entry, dict)]
        if isinstance(data.get('apps'), list):
            return [entry for entry in data['apps'] if isinstance(entry, dict)]
        return [data]

    return []


def _coerce_optional_str(value: Any) -> Optional[str]:
    return str(value) if isinstance(value, str) and value.strip() else None


def _coerce_required_str(value: Any, field: str) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise AppRepoSpecError(f"Repo entry missing required '{field}' field")


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    raise AppRepoSpecError("Manifest depth must be an integer")


def _manifest_root_from(manifests: Dict[str, Any], path_value: Optional[str]) -> Optional[str]:
    if not manifests:
        return path_value
    root = manifests.get('root')
    if isinstance(root, str) and root.strip():
        return root
    return path_value


def _load_from_spec_reference(
    data: Dict[str, Any],
    *,
    base_path: Optional[Path],
) -> AppRepoSpec:
    spec_path = _coerce_required_str(data.get('spec'), 'spec')
    resolved_path = Path(spec_path).expanduser()
    if base_path and not resolved_path.is_absolute():
        resolved_path = (base_path / spec_path).expanduser()

    select_name = _coerce_optional_str(data.get('select')) or _coerce_optional_str(data.get('name'))
    referenced = load_app_repo_spec(str(resolved_path), name=select_name)

    manifests_override = data.get('manifests') if isinstance(data.get('manifests'), dict) else {}

    return AppRepoSpec(
        name=_coerce_optional_str(data.get('alias')) or _coerce_optional_str(data.get('name')) or referenced.name,
        target=_coerce_optional_str(data.get('target')) or referenced.target,
        repo=_coerce_optional_str(data.get('repo')) or referenced.repo,
        branch=_coerce_optional_str(data.get('branch')) or referenced.branch,
        path=_coerce_optional_str(data.get('path')) or referenced.path,
        manifest_root=_manifest_root_from(manifests_override, referenced.manifest_root or referenced.path),
        manifest_glob=_coerce_optional_str(manifests_override.get('glob')) or referenced.manifest_glob,
        manifest_depth=_coerce_optional_int(manifests_override.get('depth')) if manifests_override.get('depth') is not None else referenced.manifest_depth,
    )


def load_app_repo_spec(spec_path: str, name: Optional[str] = None) -> AppRepoSpec:
    """Load an app repository specification from YAML.

    Args:
        spec_path: Path to YAML file containing repo definitions.
        name: Optional name to select when multiple repos defined.

    Returns:
        Parsed `AppRepoSpec`.

    Raises:
        AppRepoSpecError: On missing files, invalid formats, or selection issues.
    """
    path = Path(spec_path).expanduser()
    if not path.exists():
        raise AppRepoSpecError(f"Spec file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise AppRepoSpecError(f"Failed to parse spec YAML: {exc}") from exc

    entries = _normalize_entries(raw)
    if not entries:
        raise AppRepoSpecError("Spec file contains no repository definitions")

    selected: Optional[Dict[str, Any]] = None

    if name:
        for entry in entries:
            if entry.get('name') == name:
                selected = entry
                break
        if selected is None:
            defined = ', '.join(sorted(_safe_name(entry) for entry in entries))
            raise AppRepoSpecError(
                f"Spec does not define a repo named '{name}'. Available: {defined}"
            )
    else:
        if len(entries) > 1:
            defined = ', '.join(sorted(_safe_name(entry) for entry in entries))
            raise AppRepoSpecError(
                "Spec defines multiple repos; use --name to select one. "
                f"Available: {defined}"
            )
        selected = entries[0]

    if not isinstance(selected, dict):
        raise AppRepoSpecError("Selected repo entry must be a mapping")

    return AppRepoSpec.from_dict(selected)


def _safe_name(entry: Dict[str, Any]) -> str:
    value = entry.get('name')
    return str(value) if value else '<unnamed>'


def iter_app_repo_specs(data: Iterable[Dict[str, Any]], *, base_path: Optional[Path] = None) -> List[AppRepoSpec]:
    """Parse iterable of repo definitions into specs."""

    specs: List[AppRepoSpec] = []
    for idx, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise AppRepoSpecError(f"Repo entry at index {idx} must be a mapping")
        specs.append(AppRepoSpec.from_dict(entry, base_path=base_path))
    return specs
