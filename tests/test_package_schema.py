"""Schema sanity checks for package YAMLs."""
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGES_DIR = REPO_ROOT / "packages"


def load_package(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) or {}


def test_packages_have_required_fields():
    """All package files must declare name and type; OCI packages need oci.image."""
    pkg_files = sorted(PACKAGES_DIR.glob("*.yml"))
    assert pkg_files, "No packages found to validate"

    for pkg_file in pkg_files:
        data = load_package(pkg_file)
        assert "name" in data and data["name"], f"{pkg_file.name} missing name"
        assert "type" in data and data["type"], f"{pkg_file.name} missing type"

        if data.get("type") == "oci":
            oci = data.get("oci", {})
            assert isinstance(oci, dict), f"{pkg_file.name} oci section must be a mapping"
            assert oci.get("image"), f"{pkg_file.name} missing oci.image"
