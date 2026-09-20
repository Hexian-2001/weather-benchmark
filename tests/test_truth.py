"""Unit tests for benchmark.truth."""

import numpy as np
import pandas as pd
import xarray as xr

from benchmark import truth


def _era5_like(tmp_path):
    """A WeatherBench-2-style ERA5 netCDF: ``latitude``/``longitude`` coords, long names."""
    lat = np.linspace(60.0, 10.0, 6)          # descending, like ERA5
    lon = np.linspace(60.0, 150.0, 10)
    time = pd.date_range("2023-01-01", periods=8, freq="6h").values
    levels = [500, 850]
    surf = xr.DataArray(
        np.ones((len(time), len(lat), len(lon))),
        dims=("time", "latitude", "longitude"),
        coords={"time": time, "latitude": lat, "longitude": lon},
    )
    atmos = xr.DataArray(
        np.ones((len(time), len(levels), len(lat), len(lon))),
        dims=("time", "level", "latitude", "longitude"),
        coords={"time": time, "level": levels, "latitude": lat, "longitude": lon},
    )
    ds = xr.Dataset({"2m_temperature": surf, "geopotential": atmos})
    path = tmp_path / "era5.nc"
    ds.to_netcdf(path)
    return path


def test_load_truth_normalizes_coords_and_folds_levels(tmp_path):
    ds = truth.load_truth(
        _era5_like(tmp_path), region={"lat": (15.0, 55.0), "lon": (70.0, 140.0)}
    )
    assert "lat" in ds.coords and "lon" in ds.coords
    assert "latitude" not in ds.coords and "longitude" not in ds.coords
    assert "geopotential_500" in ds.data_vars
    assert "level" not in ds.dims
    # region selection reduced the grid
    assert float(ds["lat"].min()) >= 15.0
    assert float(ds["lat"].max()) <= 55.0


def test_load_truth_filters_variables(tmp_path):
    ds = truth.load_truth(_era5_like(tmp_path), variables=["2m_temperature"])
    assert list(ds.data_vars) == ["2m_temperature"]
