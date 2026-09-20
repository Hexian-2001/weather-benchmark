"""Leaderboard: rebuild the leaderboard and generate a report (Phase 2).

Contract:
- comparable only under the same convention: same year / region / regrid / metric set;
- the leaderboard records model_id + version + score_id + config hash; config changes
  create new rows, never overwriting;
- ranking dimensions: primary metrics (RMSE / ACC) split by variable, period, and region.
"""

from __future__ import annotations

from typing import Any, Dict


def rebuild_leaderboard(scores_dir: str, cfg: Dict[str, Any]):
    """Aggregate all scores into a leaderboard.json snapshot."""
    raise NotImplementedError("report will be implemented in Phase 2.")
