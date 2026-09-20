"""Climatology: 30-yr daily climatology (1991–2020) for ACC and the climatology baseline.

Contract:
- input ERA5, average across years per day-of-year → a 365-day daily climatology;
- precomputed and cached; the scoring stage only reads the cache and does pure computation;
- the CLI builder lives at ``scripts/build_climatology.py``.
"""

from __future__ import annotations

import xarray as xr


def build_daily_climatology(
    ds: xr.Dataset,
    period: tuple[int, int],
    variables: list[str],
    smooth: int = 0,
) -> xr.Dataset:
    """Build the 365-day daily climatology from hourly (or finer) data.

    Parameters
    ----------
    ds : xarray.Dataset
        Data with a ``time`` dim. Region selection is the caller's job; this function
        does year selection, variable selection, and the day-of-year reduction.
    period : tuple[int, int]
        (start_year, end_year), inclusive.
    variables : list[str]
        Variable names to keep; any name not present in ``ds`` is ignored.
    smooth : int, optional
        Day-of-year sliding-mean window (odd); 0 or 1 disables smoothing.

    Returns
    -------
    xarray.Dataset
        Climatology indexed by ``dayofyear`` (365 days), one mean per calendar day.
    """
    start, end = period
    ds = ds.sel(time=slice(f"{start}-01-01", f"{end}-12-31"))
    ds = ds[[v for v in variables if v in ds]]

    daily = ds.resample(time="1D").mean("time")
    doy = daily["time.dayofyear"]
    climatology = daily.groupby(doy).mean("time")

    # fold the leap day (Feb 29) away by dropping day 366, keeping 365 days
    climatology = climatology.sel(dayofyear=climatology.dayofyear != 366)

    if smooth and smooth > 1:
        climatology = climatology.rolling(dayofyear=smooth, center=True, min_periods=1).mean()

    return climatology
