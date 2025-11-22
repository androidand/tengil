"""Tests for OCI capability detection helper."""
from tengil.services.oci_capability import OciCapability, detect_oci_support


def test_detect_oci_support_mock():
    cap = detect_oci_support(mock=True)
    assert isinstance(cap, OciCapability)
    assert cap.supported is True
    assert cap.pve_version == "9.1 (mock)"
    assert "mock" in cap.reason
