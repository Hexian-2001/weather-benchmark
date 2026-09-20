"""Scoring: map (predictions, truth, climatology, config) to metrics.

Contract:
- scoring is a **pure function**, replayable: same input → same output;
- produces a metric cube (dims metric × variable × lead_time) + a summary dict;
- the full orchestration (ingest → regrid → metrics → write) lives in the CLI; this
  module only computes metrics from aligned inputs.

Derived metrics (wind_vector_RMSE, skill_score) are deferred to the report stage,
where baselines are available.
"""

from __future__ import annotations

from typing import Any, Dict

import xarray as xr

from . import metrics


def _metric_funcs():
    return {
        "RMSE": metrics.rmse,
        "ACC": metrics.acc,
        "MAE": metrics.mae,
        "bias": metrics.bias,
    }


def score(pred, truth, climatology, cfg: Dict[str, Any], variables: list[str] | None = None):
    """Compute metrics from aligned ``pred`` / ``truth`` / ``climatology``.

    Parameters
    ----------
    pred, truth, climatology : xarray.Dataset
        Same canonical variable names (levels already folded into names) and the same
        dims, ending in ``(..., lead_time, lat, lon)``. ``climatology`` must already be
        broadcast to ``pred``/``truth`` (aligned along ``lead_time``).
    cfg : dict
        The benchmark config; ``metrics.primary`` + ``metrics.auxiliary`` are computed.
    variables : list[str], optional
        Restrict scoring to these canonical variable names. Defaults to the variables
        common to ``pred`` and ``truth``.

    Returns
    -------
    (metric_cube, summary)
        ``metric_cube`` is an xarray.DataArray with dims ``(metric, variable, lead_time)``;
        ``summary`` is a dict of overall means keyed by ``"<metric>/<variable>"``.
    """
    names = list(cfg["metrics"]["primary"]) + list(cfg["metrics"]["auxiliary"])
    funcs = _metric_funcs()
    common = [v for v in pred.data_vars if v in truth.data_vars]
    if variables is not None:
        variables = [v for v in variables if v in common]
    else:
        variables = common

    per_metric = {}
    for m in names:
        fn = funcs[m]
        pieces = []
        for var in variables:
            if m == "ACC":
                pieces.append(fn(pred[var], truth[var], climatology[var]))
            else:
                pieces.append(fn(pred[var], truth[var]))
        # ``xr.concat`` does not create string coordinate labels from DataArray names,
        # so assign the ``variable`` coordinate explicitly.
        per_metric[m] = xr.concat(pieces, dim="variable").assign_coords(variable=variables)

    metric_cube = xr.concat([per_metric[m] for m in names], dim="metric").assign_coords(
        metric=names
    )

    summary = {
        f"{m}/{var}": float(metric_cube.sel(metric=m, variable=var).mean())
        for m in names
        for var in variables
    }

    return metric_cube, summary
