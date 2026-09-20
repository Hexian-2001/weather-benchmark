"""Truth & climatology loading (Phase 1).

The ground truth is ERA5 (primary) / IFS HRES analysis (near-real-time check), cached in
WeatherBench 2 conventions: ``latitude``/``longitude`` coordinates and long variable names
(``2m_temperature``, ``geopotential`` + ``level``, ...). This module normalizes those onto the
benchmark's internal ``lat``/``lon`` convention and selects region / variables / time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import xarray as xr

from .ingest import canonicalize_variables, normalize_spatial


def _open(path: Path) -> xr.Dataset:
    """Open a truth/climatology store: a zarr store, a single netCDF, or a directory of shards.

    Loading is eager (no dask dependency): scoring reads a pre-consolidated cache, so the
    directory-of-shards case is a convenience for the download stage rather than the hot path.
    """
    path = Path(path)
    if path.is_dir():
        if (path / ".zarray").exists() or (path / ".zgroup").exists():
            return xr.open_zarr(path)
        files = sorted(path.glob("*.nc"))
        if not files:
            raise FileNotFoundError(f"no truth files (*.nc) under {path}")
        if len(files) == 1:
            return xr.open_dataset(files[0])
        return xr.combine_by_coords([xr.open_dataset(f) for f in files])
    if path.suffix == ".zarr":
        return xr.open_zarr(path)
    return xr.open_dataset(path)


def select_region(ds: xr.Dataset, region: dict[str, tuple[float, float]]) -> xr.Dataset:
    """Select the ``{"lat": (s, n), "lon": (w, e)}`` box (coords must already be ``lat``/``lon``)."""
    return ds.sel(
        lat=slice(region["lat"][0], region["lat"][1]),
        lon=slice(region["lon"][0], region["lon"][1]),
    )


def load_truth(
    path: Path | str,
    variables: Optional[list[str]] = None,
    region: Optional[dict[str, tuple[float, float]]] = None,
    time_slice: Optional[slice] = None,
) -> xr.Dataset:
    """Load and normalize truth (ERA5/IFS) onto ``lat``/``lon`` with canonical variable names."""
    ds = canonicalize_variables(normalize_spatial(_open(path)))
    if region is not None:
        ds = select_region(ds, region)
    if time_slice is not None:
        ds = ds.sel(time=time_slice)
    if variables:
        ds = ds[[v for v in variables if v in ds]]
    return ds


def load_climatology(
    path: Path | str, variables: Optional[list[str]] = None
) -> xr.Dataset:
    """Load a prebuilt climatology netCDF (see ``scripts/build_climatology.py``)."""
    ds = canonicalize_variables(normalize_spatial(_open(path)))
    if variables:
        ds = ds[[v for v in variables if v in ds]]
    return ds
