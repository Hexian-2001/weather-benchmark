"""Unit tests for benchmark.regrid (requires xarray-regrid)."""

import numpy as np
import pytest
import xarray as xr

from benchmark import regrid


@pytest.fixture
def fine_grid():
    # 0.1° grid padded with a half-cell margin so the coarser target interior is covered
    lat = np.arange(14.8, 25.2, 0.1)
    lon = np.arange(69.8, 80.2, 0.1)
    data = np.ones((len(lat), len(lon)))
    return xr.DataArray(data, dims=("lat", "lon"), coords={"lat": lat, "lon": lon})


def test_regrid_resolution(fine_grid):
    out = regrid.conservative_regrid(fine_grid, target_grid_deg=0.25)
    assert np.allclose(np.diff(out["lat"].values), 0.25)
    assert np.allclose(np.diff(out["lon"].values), 0.25)


def test_regrid_preserves_constant(fine_grid):
    out = regrid.conservative_regrid(fine_grid, target_grid_deg=0.25)
    # the interior (the real region) must preserve the constant exactly and be NaN-free
    interior = out.isel(lat=slice(1, -1), lon=slice(1, -1))
    assert not np.isnan(interior).any()
    assert np.allclose(interior.values, 1.0)


def test_regrid_unsupported_method(fine_grid):
    with pytest.raises(ValueError):
        regrid.conservative_regrid(fine_grid, target_grid_deg=0.25, method="bogus")
