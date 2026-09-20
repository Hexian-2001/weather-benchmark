"""Unit tests for benchmark.ingest."""

import numpy as np
import xarray as xr

from benchmark import ingest


def _prediction(init, lat, lon, lead, levels=(500, 850)):
    """A synthetic reforecast file in the canonical format."""
    nlead, nlat, nlon, nlev = len(lead), len(lat), len(lon), len(levels)
    coords_3d = {"lead_time": lead, "lat": lat, "lon": lon}
    surf = xr.DataArray(np.ones((nlead, nlat, nlon)), dims=("lead_time", "lat", "lon"), coords=coords_3d)
    atmos = xr.DataArray(
        np.ones((nlead, nlev, nlat, nlon)),
        dims=("lead_time", "level", "lat", "lon"),
        coords={"lead_time": lead, "level": np.asarray(levels), "lat": lat, "lon": lon},
    )
    return xr.Dataset(
        {
            "2t": surf,               # Aurora short key → 2m_temperature
            "10u": surf,              # Aurora short key → 10m_u_component_of_wind
            "geopotential": atmos,    # long name, carries a level dim
        },
        coords={"init_time": np.datetime64(init)},
    )


def test_canonicalize_variables_folds_levels_and_aliases():
    lat = np.linspace(50.0, 20.0, 3)  # descending
    lon = np.linspace(-90.0, 90.0, 4)
    ds = ingest.canonicalize_variables(_prediction("2023-01-01T00", lat, lon, [6.0, 12.0]))

    assert set(ds.data_vars) == {
        "2m_temperature",
        "10m_u_component_of_wind",
        "geopotential_500",
        "geopotential_850",
    }
    assert "level" not in ds["geopotential_500"].dims
    assert ds["geopotential_500"].dims == ("lead_time", "lat", "lon")


def test_normalize_spatial():
    lat = np.linspace(50.0, 20.0, 3)  # descending → must become ascending
    lon = np.linspace(-90.0, 90.0, 4)  # signed → must wrap to [0, 360)
    ds = ingest.normalize_spatial(_prediction("2023-01-01T00", lat, lon, [6.0]))

    assert np.all(np.diff(ds["lat"].values) > 0)          # ascending
    assert float(ds["lon"].min()) >= 0.0
    assert float(ds["lon"].max()) < 360.0


def test_load_predictions_filters_years_and_concats(tmp_path):
    results = tmp_path / "results"
    pred_dir = results / "aurora-0.25" / "predictions"
    pred_dir.mkdir(parents=True)
    lat = np.linspace(55.0, 15.0, 5)
    lon = np.linspace(70.0, 140.0, 6)
    lead = [6.0, 12.0]

    _prediction("2023-01-01T00", lat, lon, lead).to_netcdf(pred_dir / "2023010100.nc")
    _prediction("2024-01-01T00", lat, lon, lead).to_netcdf(pred_dir / "2024010100.nc")

    storage = {"results_dir": str(results)}

    ds23 = ingest.load_predictions("aurora-0.25", [2023], storage)
    assert ds23.sizes["init_time"] == 1
    assert ds23["init_time"].values[0].astype("datetime64[Y]") == np.datetime64("2023-01-01")

    ds_all = ingest.load_predictions("aurora-0.25", [2023, 2024], storage)
    assert ds_all.sizes["init_time"] == 2
    assert ds_all["lead_time"].dtype.kind == "f"          # hours as float
    assert "2m_temperature" in ds_all.data_vars
    assert "geopotential_500" in ds_all.data_vars


def _unified_foehn(init="2024-01-01T00", lead_h=(6, 12)):
    """A Foehn ``unified-forecast-1`` file: ``time`` dim of valid datetimes, scalar
    ``init_time``, ``lead_time`` coord in hours, and long variable names."""
    lat = np.linspace(55.0, 15.0, 5)   # descending (Aurora lat orientation)
    lon = np.linspace(70.0, 140.0, 6)
    init_dt = np.datetime64(init)
    time = (init_dt + np.asarray(lead_h, dtype="timedelta64[h]")).astype("datetime64[ns]")
    nlead = len(lead_h)
    surf = xr.DataArray(
        np.ones((nlead, len(lat), len(lon))),
        dims=("time", "lat", "lon"), coords={"time": time, "lat": lat, "lon": lon},
    )
    atmos = xr.DataArray(
        np.ones((nlead, 2, len(lat), len(lon))),
        dims=("time", "level", "lat", "lon"),
        coords={"time": time, "level": [500, 850], "lat": lat, "lon": lon},
    )
    return xr.Dataset(
        {"2m_temperature": surf, "geopotential": atmos},
        coords={
            "time": time, "lat": lat, "lon": lon, "level": [500, 850],
            "init_time": np.datetime64(init),
            "lead_time": ("time", np.asarray(lead_h)),
        },
    )


def test_load_predictions_reads_unified_foehn_layout(tmp_path):
    results = tmp_path / "results"
    pred_dir = results / "aurora" / "0.25-finetuned" / "2024-01-01T00Z" / "predictions"
    pred_dir.mkdir(parents=True)
    fname = "aurora_0.25-finetuned_IC2024-01-01T00_STEPS40_240h_0.25deg_china.nc"
    _unified_foehn("2024-01-01T00").to_netcdf(pred_dir / fname)

    ds = ingest.load_predictions("aurora", [2024], {"results_dir": str(results)})
    assert ds.sizes["init_time"] == 1
    assert "lead_time" in ds.dims and "time" not in ds.dims
    assert ds["lead_time"].dtype.kind == "f"
    assert list(ds["lead_time"].values) == [6.0, 12.0]
    assert "2m_temperature" in ds.data_vars
    assert "geopotential_500" in ds.data_vars
    assert "geopotential_850" in ds.data_vars
