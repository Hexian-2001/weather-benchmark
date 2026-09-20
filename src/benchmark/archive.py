"""Immutable score archive (Phase 1).

Each score is written under ``scores/<model_id>/<version>/`` as a metric cube (NetCDF) and a
``summary.json`` that records the config hash. The config hash is the evaluation fingerprint:
a config change is recorded in the summary and surfaced by the leaderboard (Phase 2), never
silently overwriting history.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import xarray as xr

from . import config as config_mod


def write_score(
    metric_cube: xr.DataArray,
    summary: Dict[str, float],
    cfg: Dict[str, Any],
    model_id: str,
    version: str,
) -> Path:
    """Atomically write a score to the archive and return the output directory."""
    out_dir = Path(cfg["storage"]["scores_dir"]) / model_id / version
    out_dir.mkdir(parents=True, exist_ok=True)

    metric_cube.to_netcdf(out_dir / "metrics.nc")

    payload = {
        "model_id": model_id,
        "version": version,
        "config_hash": config_mod.config_hash(cfg),
        "summary": summary,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )
    return out_dir
