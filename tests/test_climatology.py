"""Unit tests for benchmark.climatology."""

import pandas as pd
import xarray as xr

from benchmark import climatology


def test_build_daily_climatology_means_calendar_days():
    # 2019 + 2020 (leap) at 6-hourly resolution; value = day-of-year (constant within a day)
    time = pd.date_range("2019-01-01", "2020-12-31", freq="6h")
    doy = xr.DataArray(time.dayofyear, dims="time", coords={"time": time})
    ds = xr.Dataset({"v": doy})

    clim = climatology.build_daily_climatology(ds, period=(2019, 2020), variables=["v"])

    assert clim.sizes["dayofyear"] == 365  # leap day folded away
    assert float(clim["v"].sel(dayofyear=100)) == 100.0
    assert float(clim["v"].sel(dayofyear=365)) == 365.0


def test_build_daily_climatology_drops_missing_variables():
    time = pd.date_range("2019-01-01", "2019-12-31", freq="6h")
    doy = xr.DataArray(time.dayofyear, dims="time", coords={"time": time})
    ds = xr.Dataset({"v": doy})

    clim = climatology.build_daily_climatology(
        ds, period=(2019, 2019), variables=["v", "not_present"]
    )

    assert "v" in clim
    assert "not_present" not in clim
