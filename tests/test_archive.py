"""Unit tests for benchmark.archive."""

import json

import numpy as np
import xarray as xr

from benchmark import archive


def test_write_score(tmp_path):
    cube = xr.DataArray(
        np.ones((2, 1, 3)),
        dims=("metric", "variable", "lead_time"),
        coords={"metric": ["RMSE", "bias"], "variable": ["2m_temperature"], "lead_time": [6, 12, 18]},
    )
    cfg = {
        "storage": {"scores_dir": str(tmp_path / "scores")},
        "metrics": {"primary": ["RMSE"]},
        "years": {"test": [2023]},
    }
    out = archive.write_score(cube, {"RMSE/2m_temperature": 1.0}, cfg, "m", "1.0.0")

    assert (out / "metrics.nc").exists()
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["model_id"] == "m"
    assert payload["version"] == "1.0.0"
    assert payload["config_hash"]
    assert payload["summary"]["RMSE/2m_temperature"] == 1.0
