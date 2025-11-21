"""Capability detection for upcoming Proxmox 9.1 OCI support.

This is intentionally defensive and returns graceful fallbacks when the
environment cannot be inspected (e.g., sandboxed or non-Proxmox hosts).
"""
import re
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class OciCapability:
    supported: bool
    reason: str
    pve_version: Optional[str] = None
    hint: Optional[str] = None


def _run_cmd(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        return result.returncode, result.stdout, result.stderr
    except Exception as exc:  # pragma: no cover - defensive
        return 1, "", str(exc)


def detect_oci_support(mock: bool = False) -> OciCapability:
    """Check if the host appears to support OCI containers."""
    if mock:
        return OciCapability(True, "mock mode", pve_version="9.1 (mock)")

    # Check pveversion for 9.1+ signal
    rc, out, _ = _run_cmd(["pveversion"])
    pve_version = None
    if rc == 0 and out:
        match = re.search(r"pve-manager/([0-9.]+)", out)
        if match:
            pve_version = match.group(1)

    # Quick heuristic: pct help create should mention oci for 9.1+
    rc, pct_out, _ = _run_cmd(["pct", "help", "create"])
    if rc == 0 and "oci" in pct_out.lower():
        return OciCapability(True, "pct create supports oci", pve_version=pve_version)

    # Fallback: no direct evidence
    reason = "pct create does not mention oci" if rc == 0 else "pct unavailable"
    hint = "Upgrade to Proxmox 9.1+ and ensure oci support is enabled."
    return OciCapability(False, reason, pve_version=pve_version, hint=hint)
