"""Data ingestion: read model reforecast outputs into a unified structure (Phase 1).

Contract:
- reuses the ``foehn_core.prediction_store`` unified forecast format — no new wheel;
- reforecast outputs live at ``results/<model>/<variant>/<init>Z/predictions/``;
- produces a normalized xarray.Dataset: dims (init_time, lead_time, variable[, level], lat, lon).
"""

from __future__ import annotations

from typing import Any, Dict


def load_predictions(model_id: str, years: list[int], storage: Dict[str, Any]):
    """Read a model's reforecast predictions for the given years, returning a normalized Dataset."""
    raise NotImplementedError("ingest will be implemented in Phase 1: adapt prediction_store's unified format.")
