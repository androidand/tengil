"""Tests for ResourceValidator."""
from tengil.core.resource_validator import (
    HostResources,
    ResourceValidator,
)


def build_config(memory_vals):
    return {
        "pools": {
            "tank": {
                "datasets": {
                    f"dataset{idx}": {
                        "containers": [
                            {
                                "name": f"ct{idx}",
                                "auto_create": True,
                                "resources": {"memory": val, "cores": 2},
                            }
                        ]
                    }
                    for idx, val in enumerate(memory_vals, start=1)
                }
            }
        }
    }


def test_validator_within_limits():
    config = build_config([512, 1024])
    host = HostResources(total_memory_mb=4096, total_swap_mb=0, total_cores=8)

    result = ResourceValidator(config, host).validate()

    assert result.auto_create_count == 2
    assert result.total_memory_mb == 1536
    assert not result.errors
    assert not result.warnings


def test_validator_warns_near_limit():
    config = build_config([1900, 1800])
    host = HostResources(total_memory_mb=4096, total_swap_mb=0, total_cores=8)

    result = ResourceValidator(config, host).validate()

    assert not result.errors
    assert any("RAM" in warning for warning in result.warnings)


def test_validator_errors_when_exceeding():
    config = build_config([4096, 2048])
    host = HostResources(total_memory_mb=4096, total_swap_mb=0, total_cores=8)

    result = ResourceValidator(config, host).validate()

    assert result.has_errors()
    assert any("RAM" in error for error in result.errors)
