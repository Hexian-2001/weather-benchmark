"""Scoring: map (predictions, truth, climatology, config) to metrics (Phase 1).

Contract:
- scoring is a **pure function**, replayable: same input → same output;
- produces a metric cube (NetCDF, dims metric × var × level × lead × region) + summary.json;
- written atomically under a ``score_id``, never overwriting history.
"""

from __future__ import annotations

from typing import Any, Dict


def score(pred, truth, climatology, cfg: Dict[str, Any]):
    """Compute metrics for a set of reforecast results, returning (metric_cube, summary)."""
    raise NotImplementedError("score will be implemented in Phase 1: ingest → regrid → metrics → write.")
