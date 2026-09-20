"""Scoring pipeline orchestration (Phase 1).

Wires ``ingest → align truth/climatology → score → archive``. Each stage is a pure, testable
function; the CLI is a thin wrapper around :func:`score_model`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import xarray as xr

from . import archive, config as config_mod, ingest, score as score_mod, truth as truth_mod


def _valid_time(pred: xr.Dataset) -> xr.DataArray:
    """The valid (forecast) time of each ``(init_time, lead_time)`` sample.

    Values are ``datetime64``, but the ``lead_time`` coordinate is kept as ``pred``'s float
    hours so that the aligned truth/climatology broadcast cleanly against ``pred``.
    """
    lead = pd.to_timedelta(pred["lead_time"].values, unit="h")
    valid = pred["init_time"] + xr.DataArray(lead, dims="lead_time")
    return valid.assign_coords(lead_time=pred["lead_time"])


def align_truth(pred: xr.Dataset, truth: xr.Dataset) -> xr.Dataset:
    """Select truth at the predictions' valid times (``init_time + lead_time``)."""
    return truth.sel(time=_valid_time(pred))


def align_climatology(pred: xr.Dataset, climatology: xr.Dataset) -> xr.Dataset:
    """Select climatology at the predictions' valid (day-of-year[, hour]).

    If the climatology carries an ``hour`` coordinate it is used; otherwise only day-of-year is
    selected (a daily climatology — the diurnal cycle is then not represented).
    """
    valid = _valid_time(pred)
    doy = valid.dt.dayofyear
    if "hour" in climatology.coords:
        return climatology.sel(dayofyear=doy, hour=valid.dt.hour)
    return climatology.sel(dayofyear=doy)


def validate_predictions(pred: xr.Dataset, cfg: Dict[str, Any]) -> List[str]:
    """Check init-time and lead-time coverage against the config. Returns a list of issues."""
    issues: List[str] = []
    expected_hours = {int(h) for h in cfg["time"]["init_times"]}
    for hour in pred["init_time"].dt.hour.values:
        if int(hour) not in expected_hours:
            issues.append(f"unexpected init hour {int(hour)} (expected {sorted(expected_hours)})")

    step_6h = cfg["time"]["horizons"]["step_6h"]
    expected_leads = set(range(step_6h["lead_step_h"], step_6h["horizon_h"] + 1, step_6h["lead_step_h"]))
    got = {int(x) for x in pred["lead_time"].values}
    missing = expected_leads - got
    if missing:
        issues.append(f"missing lead times (hours): {sorted(missing)}")
    return issues


def score_model(model_id: str, version: str, cfg: Dict[str, Any]) -> Path:
    """Run the full scoring pipeline and archive the result. Returns the output directory."""
    variables = config_mod.variables_from_config(cfg)
    region = config_mod.region_from_config(cfg)
    storage = cfg["storage"]
    years = cfg["years"]["test"]

    pred = ingest.load_predictions(model_id, years, storage)
    truth = truth_mod.load_truth(storage["truth_dir"], variables=variables, region=region)
    climatology = truth_mod.load_climatology(storage["climatology_dir"], variables=variables)

    truth = align_truth(pred, truth)
    climatology = align_climatology(pred, climatology)

    metric_cube, summary = score_mod.score(pred, truth, climatology, cfg, variables=variables)
    return archive.write_score(metric_cube, summary, cfg, model_id, version)
