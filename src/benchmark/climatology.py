"""Climatology: 30-yr daily climatology (1991–2020) for ACC and the climatology baseline (Phase 1).

Contract:
- input ERA5, average across years per day-of-year → a 365-day daily climatology;
- precomputed and cached; the scoring stage only reads the cache and does pure computation;
- see ``scripts/build_climatology.py`` for the builder.
"""

from __future__ import annotations

from typing import Any, Dict


def build_daily_climatology(ds, period: tuple[int, int], variables: list[str]):
    """Build the daily climatology from hourly ERA5 data."""
    raise NotImplementedError("climatology will be implemented in Phase 1; script at scripts/build_climatology.py")
