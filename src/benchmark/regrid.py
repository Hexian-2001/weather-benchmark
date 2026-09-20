"""Regrid: bring native resolution onto the 0.25° common comparison grid (Phase 1).

Contract:
- 0.1° models: scored once at native resolution, then once after first-order
  conservative remapping to 0.25°;
- remapping is first-order conservative (consistent with WeatherBench 2);
- truth / climatology are likewise regridded once and cached.
"""

from __future__ import annotations

from typing import Any, Dict


def conservative_regrid(ds, target_grid_deg: float = 0.25, method: str = "conservative"):
    """First-order conservative remapping onto the target grid."""
    raise NotImplementedError("regrid will be implemented in Phase 1: first-order conservative remapping.")
