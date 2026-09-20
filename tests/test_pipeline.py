"""Unit + integration tests for benchmark.pipeline."""

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from benchmark import pipeline


def _cfg(storage):
    return {
        "variables": {"surface": ["2m_temperature"], "pressure": []},
        "region": {"lat": [15.0, 55.0], "lon": [70.0, 140.0]},
        "years": {"test": [2023]},
        "time": {
            "init_times": ["00", "12"],
            "horizons": {"step_6h": {"lead_step_h": 6, "horizon_h": 240}},
        },
        "metrics": {"primary": ["RMSE", "ACC"], "auxiliary": ["MAE", "bias"]},
        "storage": storage,
    }


def _pred(init_hours=(0, 12), leads=range(6, 241, 6)):
    init = np.array([f"2023-01-01T{h:02d}" for h in init_hours], dtype="datetime64[h]")
    lead = np.array(list(leads), dtype=float)
    data = np.zeros((len(init), len(lead), 2, 2))
    return xr.Dataset(
        {"2m_temperature": (("init_time", "lead_time", "lat", "lon"), data)},
        coords={"init_time": init, "lead_time": lead, "lat": [15, 20], "lon": [70, 75]},
    )


def test_validate_predictions_complete():
    cfg = _cfg({})
    assert pipeline.validate_predictions(_pred(), cfg) == []


def test_validate_predictions_missing_lead():
    cfg = _cfg({})
    issues = pipeline.validate_predictions(_pred(leads=range(6, 121, 6)), cfg)
    assert any("lead" in issue for issue in issues)


def test_align_truth_selects_valid_times():
    init = np.array(["2023-01-01T00", "2023-01-01T12"], dtype="datetime64[h]")
    pred = xr.Dataset(
        {"v": (("init_time", "lead_time", "lat", "lon"), np.zeros((2, 2, 1, 1)))},
        coords={"init_time": init, "lead_time": [6.0, 12.0], "lat": [15], "lon": [70]},
    )
    times = pd.date_range("2023-01-01T00", periods=8, freq="6h").values
    truth = xr.Dataset(
        {"v": (("time", "lat", "lon"), np.arange(len(times)).reshape(-1, 1, 1))},
        coords={"time": times, "lat": [15], "lon": [70]},
    )
    aligned = pipeline.align_truth(pred, truth)
    assert aligned["v"].dims == ("init_time", "lead_time", "lat", "lon")
    # valid times = 06, 12, 18, 24 (2nd..5th truth samples)
    assert aligned["v"].isel(init_time=0, lead_time=0).values[0, 0] == 1.0


def test_score_model_end_to_end(tmp_path):
    root = tmp_path
    storage = {
        "results_dir": str(root / "results"),
        "truth_dir": str(root / "truth"),
        "climatology_dir": str(root / "climatology"),
        "scores_dir": str(root / "scores"),
    }

    # 1. predictions: one init (2023-01-01T00), leads 6/12, constant 3.0
    pred_dir = Path(storage["results_dir"]) / "m" / "predictions"
    pred_dir.mkdir(parents=True)
    lat = np.array([20.0, 15.0])
    lon = np.array([70.0, 75.0])
    surf = xr.DataArray(
        np.full((2, 2, 2), 3.0),
        dims=("lead_time", "lat", "lon"),
        coords={"lead_time": [6.0, 12.0], "lat": lat, "lon": lon},
    )
    xr.Dataset({"2t": surf}, coords={"init_time": np.datetime64("2023-01-01T00")}).to_netcdf(
        pred_dir / "2023010100.nc"
    )

    # 2. truth: 2m_temperature = 1.0, 6-hourly over Jan 1
    Path(storage["truth_dir"]).mkdir(parents=True)
    time = pd.date_range("2023-01-01T00", periods=4, freq="6h").values
    truth_ds = xr.Dataset(
        {"2m_temperature": (("time", "lat", "lon"), np.full((len(time), 2, 2), 1.0))},
        coords={"time": time, "lat": lat, "lon": lon},
    )
    truth_ds.to_netcdf(Path(storage["truth_dir"]) / "era5.nc")

    # 3. climatology: 2m_temperature = 0.0 by day-of-year
    Path(storage["climatology_dir"]).mkdir(parents=True)
    clim_ds = xr.Dataset(
        {"2m_temperature": (("dayofyear", "lat", "lon"), np.zeros((365, 2, 2)))},
        coords={"dayofyear": np.arange(1, 366), "lat": lat, "lon": lon},
    )
    clim_ds.to_netcdf(Path(storage["climatology_dir"]) / "clim.nc")

    out_dir = pipeline.score_model("m", "1.0.0", _cfg(storage))

    assert (out_dir / "metrics.nc").exists()
    assert (out_dir / "summary.json").exists()

    cube = xr.open_dataarray(out_dir / "metrics.nc")
    assert set(cube["metric"].values) == {"RMSE", "ACC", "MAE", "bias"}
    assert list(cube["variable"].values) == ["2m_temperature"]
    # pred=3, truth=1 → RMSE=MAE=2, bias=+2, ACC=1
    assert np.allclose(cube.sel(metric="RMSE", variable="2m_temperature").values, 2.0)
    assert np.allclose(cube.sel(metric="bias", variable="2m_temperature").values, 2.0)
    assert np.allclose(cube.sel(metric="ACC", variable="2m_temperature").values, 1.0)
