"""Unit tests for benchmark.score."""

import numpy as np
import xarray as xr

from benchmark import score as score_mod


def _cfg():
    return {"metrics": {"primary": ["RMSE", "ACC"], "auxiliary": ["MAE", "bias"]}}


def test_score_structure_and_constant_error():
    lead = np.array([6.0, 12.0, 18.0, 24.0])
    lat = np.linspace(-45.0, 45.0, 8)
    lon = np.linspace(0.0, 30.0, 12)
    rng = np.random.default_rng(0)
    shape = (len(lead), len(lat), len(lon))
    coords = {"lead_time": lead, "lat": lat, "lon": lon}

    truth_t2m = xr.DataArray(rng.normal(size=shape), dims=("lead_time", "lat", "lon"), coords=coords)
    truth_z500 = xr.DataArray(rng.normal(size=shape), dims=("lead_time", "lat", "lon"), coords=coords)

    pred = xr.Dataset({"2m_temperature": truth_t2m + 2.0, "geopotential_500": truth_z500 - 1.0})
    truth = xr.Dataset({"2m_temperature": truth_t2m, "geopotential_500": truth_z500})
    clim = xr.Dataset(
        {
            "2m_temperature": xr.zeros_like(truth_t2m),
            "geopotential_500": xr.zeros_like(truth_z500),
        }
    )

    cube, summary = score_mod.score(pred, truth, clim, _cfg())

    assert list(cube.dims) == ["metric", "variable", "lead_time"]
    assert set(cube["metric"].values) == {"RMSE", "ACC", "MAE", "bias"}
    assert set(cube["variable"].values) == {"2m_temperature", "geopotential_500"}

    # t2m: constant +2.0 error → RMSE == 2, bias == +2
    assert np.allclose(cube.sel(metric="RMSE", variable="2m_temperature").values, 2.0)
    assert np.allclose(cube.sel(metric="bias", variable="2m_temperature").values, 2.0)
    # z500: constant -1.0 error → RMSE == 1, bias == -1
    assert np.allclose(cube.sel(metric="RMSE", variable="geopotential_500").values, 1.0)
    assert np.allclose(cube.sel(metric="bias", variable="geopotential_500").values, -1.0)

    assert np.isclose(summary["RMSE/2m_temperature"], 2.0)
    assert np.isclose(summary["bias/geopotential_500"], -1.0)
