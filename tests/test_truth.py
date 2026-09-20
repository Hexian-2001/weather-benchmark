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


def _cds_like(tmp_path):
    """A new-CDS ERA5 netCDF: ``valid_time``/``pressure_level`` coords, short names, metadata."""
    lat = np.linspace(55.0, 15.0, 5)
    lon = np.linspace(70.0, 140.0, 8)
    valid_time = pd.date_range("2024-01-01", periods=4, freq="6h").values
    levels = [500, 850]
    ds = xr.Dataset(
        {
            "t2m": (("valid_time", "latitude", "longitude"), np.ones((4, 5, 8))),
            "z": (("valid_time", "pressure_level", "latitude", "longitude"),
                  np.ones((4, 2, 5, 8))),
        },
        coords={
            "valid_time": valid_time,
            "pressure_level": levels,
            "latitude": lat,
            "longitude": lon,
            "number": 0,
            "expver": ("valid_time", np.ones(4, dtype=int)),
        },
    )
    path = tmp_path / "era5_cds.nc"
    ds.to_netcdf(path)
    return path


def test_load_truth_normalizes_cds_format(tmp_path):
    ds = truth.load_truth(_cds_like(tmp_path))
    assert "time" in ds.coords and "valid_time" not in ds.coords
    assert "2m_temperature" in ds.data_vars and "t2m" not in ds.data_vars
    assert "geopotential_500" in ds.data_vars
    assert "level" not in ds.dims
    assert "expver" not in ds.coords and "number" not in ds.coords
