"""Shared drift helper utilities for CLI modules."""
from __future__ import annotations

from typing import Optional, Tuple, TYPE_CHECKING

from tengil.core.drift_engine import DriftEngine, DriftReport
from tengil.core.state_store import StateStore

if TYPE_CHECKING:
    from tengil.config.loader import ConfigLoader


def analyze_drift(
    loader: Optional["ConfigLoader"],
    state_store: Optional[StateStore] = None,
) -> Tuple[Optional[DriftReport], Optional[str]]:
    """Return (DriftReport, status) to enable drift-aware CLI messaging."""
    if loader is None:
        return None, "no-loader"

    try:
        desired_state = loader.build_desired_state()
    except Exception:
        return None, "desired-error"

    store = state_store or StateStore()
    reality_snapshot = store.get_last_reality_snapshot()
    if not reality_snapshot:
        return None, "missing-snapshot"

    report = DriftEngine(desired_state, reality_snapshot).run()
    return report, None
