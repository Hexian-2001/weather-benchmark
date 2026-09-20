"""Data ingestion: read reforecast predictions into a canonical Dataset (Phase 1).

Contract:
- The canonical prediction format is the Foehn ``foehn_core.prediction_store``
  ``unified-forecast-1`` layout: one netCDF per initialization time at
  ``results/<model>/<variant>/<init>Z/predictions/``, named
  ``<model>_<variant>_IC<init>_STEPS<n>_<horizon>h_<res>deg_<region>.nc``. Each file carries a
  ``time`` dimension of valid datetimes, a scalar ``init_time`` coordinate, and a ``lead_time``
  coordinate in hours. This module walks that tree (recursively) and normalizes it onto the
  benchmark convention. Legacy flat layouts (``*.nc`` per init) are also accepted.
- Variable names use WeatherBench 2 long names (``2m_temperature``, ``geopotential`` + ``level``,
  ...). Aurora's short ``Batch`` keys (``2t``, ``10u``, ``msl``, ``z``, ``t``, ...) are mapped
  here via :data:`VARIABLE_ALIASES`.
- Output normalization: latitude ascending (south→north), longitude wrapped to [0, 360), and
  pressure levels folded into variable names (``geopotential_500``). The returned Dataset has
  canonical variable names and dims ``(init_time, lead_time[, level], lat, lon)``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import xarray as xr

# Short keys → WeatherBench 2 / ERA5 long names. Covers both Aurora ``Batch`` keys
# (``2t``/``10u``/``10v``) and the new CDS netCDF short names (``t2m``/``u10``/``v10``/``sp``).
VARIABLE_ALIASES: Dict[str, str] = {
    # surface
    "2t": "2m_temperature",                # Aurora Batch
    "t2m": "2m_temperature",               # CDS ERA5 / ERA5-Land
    "10u": "10m_u_component_of_wind",      # Aurora Batch
    "u10": "10m_u_component_of_wind",      # CDS ERA5 / ERA5-Land
    "10v": "10m_v_component_of_wind",      # Aurora Batch
    "v10": "10m_v_component_of_wind",      # CDS ERA5 / ERA5-Land
    "msl": "mean_sea_level_pressure",
    "sp": "surface_pressure",              # CDS ERA5-Land (no MSLP)
    # atmospheric (Aurora Batch and CDS ERA5 share these short names)
    "z": "geopotential",
    "t": "temperature",
    "u": "u_component_of_wind",
    "v": "v_component_of_wind",
    "q": "specific_humidity",
}


def canonicalize_variables(ds: xr.Dataset) -> xr.Dataset:
    """Rename short keys to long names and fold pressure levels into variable names.

    A variable carrying a ``level`` dimension (e.g. ``geopotential``) becomes one variable per
    level (``geopotential_500``, ``geopotential_850``, ...). Variables without a ``level``
    dimension are kept as-is. The ``init_time`` coordinate is preserved when present.
    """
    rename = {k: v for k, v in VARIABLE_ALIASES.items() if k in ds.data_vars}
    ds = ds.rename(rename)

    data_vars: Dict[str, xr.DataArray] = {}
    for name in ds.data_vars:
        da = ds[name]
        if "level" in da.dims:
            for lev in da["level"].values:
                data_vars[f"{name}_{int(lev)}"] = da.sel(level=lev, drop=True)
        else:
            data_vars[name] = da

    coords = {c: ds[c] for c in ds.coords if c not in ("level",)}
    return xr.Dataset(data_vars, coords=coords, attrs=ds.attrs)


def normalize_spatial(ds: xr.Dataset) -> xr.Dataset:
    """Normalize spatial coordinates: rename ``latitude``/``longitude`` → ``lat``/``lon``,
    sort latitude ascending, and wrap longitude to [0, 360)."""
    rename = {src: dst for src, dst in (("latitude", "lat"), ("longitude", "lon"))
              if src in ds.coords and dst not in ds.coords}
    if rename:
        ds = ds.rename(rename)
    if "lat" in ds.coords:
        ds = ds.sortby("lat")  # ascending (south → north)
    if "lon" in ds.coords:
        lon = ds["lon"]
        if float(lon.min()) < 0:
            ds = ds.assign_coords(lon=((lon + 360.0) % 360.0)).sortby("lon")
    return ds


def _normalize_lead_time(ds: xr.Dataset) -> xr.Dataset:
    """Normalize the lead dimension onto a ``lead_time`` coordinate in hours.

    Foehn ``unified-forecast-1`` files use a ``time`` dimension of valid datetimes plus a
    ``lead_time`` coordinate; the benchmark canonical form uses ``lead_time`` itself as the
    dimension. This is a no-op on files already in the canonical form.
    """
    if "lead_time" in ds.dims:
        return ds
    if "time" in ds.dims and "lead_time" in ds.coords:
        lead = ds["lead_time"].values  # plain array of hours, avoids a name/dim clash
        ds = ds.drop_vars(["time", "lead_time"])
        ds = ds.rename({"time": "lead_time"})
        return ds.assign_coords(lead_time=("lead_time", lead))
    return ds


# Foehn unified filename carries the init time as ``_IC<YYYY-MM-DDTHH>_``.
_IC_RE = re.compile(r"_IC(\d{4}-\d{2}-\d{2}T\d{2})_")


def _init_time(ds: xr.Dataset, path: Path) -> pd.Timestamp:
    """Resolve the initialization time of one prediction file.

    Preference order: an ``init_time`` / ``forecast_reference_time`` coordinate, then the
    filename (``YYYYMMDDHH``, ``YYYY-MM-DDTHH`` or ``YYYYMMDD``).
    """
    for name in ("init_time", "forecast_reference_time", "analysis_time"):
        if name in ds.coords and ds[name].size == 1:
            return pd.Timestamp(np.atleast_1d(ds[name].values)[0])

    m = _IC_RE.search(path.name)
    if m:
        return pd.Timestamp(m.group(1))

    m = re.search(r"(\d{8})(?:[-_T]?(\d{2}))?", path.name)
    if m:
        stamp = m.group(1) + (m.group(2) or "00")
        return pd.Timestamp(stamp)

    raise ValueError(f"cannot determine init_time for {path}; add an init_time coordinate")


def _lead_hours(ds: xr.Dataset) -> xr.DataArray:
    """Return the lead-time coordinate in hours (float)."""
    if "lead_time" not in ds.coords:
        raise ValueError("prediction files must have a lead_time coordinate")
    lt = ds["lead_time"]
    if np.issubdtype(lt.dtype, np.timedelta64):
        return lt / np.timedelta64(1, "h")
    return lt.astype(float)


def _discover_files(root: Path) -> List[Path]:
    """List prediction files (``.nc`` / ``.zarr``) under the predictions root.

    Walks recursively so both the Foehn ``unified-forecast-1`` tree
    (``<model>/<variant>/<init>Z/predictions/*.nc``) and a flat legacy layout are found.
    """
    if not root.is_dir():
        raise FileNotFoundError(f"predictions root not found: {root}")
    files = sorted(root.rglob("*.nc")) + sorted(root.rglob("*.zarr"))
    if not files:
        raise FileNotFoundError(f"no prediction files (*.nc/*.zarr) under {root}")
    return files


def load_predictions(
    model_id: str, years: list[int], storage: Dict[str, Any]
) -> xr.Dataset:
    """Read a model's reforecast predictions for the given years into a canonical Dataset.

    Returns a Dataset with canonical variable names (levels folded), dims
    ``(init_time, lead_time, lat, lon)`` and an ``init_time`` dimension built from the
    per-file ``init_time`` coordinates.
    """
    # ``model_id`` may be a nested subpath (e.g. ``aurora/0.25-finetuned`` for the Foehn
    # results tree); the walk below finds ``predictions/*.nc`` at any depth.
    root = Path(storage["results_dir"]) / model_id
    datasets = []
    for path in _discover_files(root):
        ds = _normalize_lead_time(canonicalize_variables(normalize_spatial(xr.open_dataset(path))))
        init = _init_time(ds, path)
        if init.year not in years:
            continue
        # promote the scalar init_time to a dimension
        ds = ds.assign_coords(init_time=np.datetime64(init)).expand_dims("init_time")
        ds = ds.assign_coords(lead_time=_lead_hours(ds))
        datasets.append(ds)

    if not datasets:
        raise FileNotFoundError(
            f"no predictions for years {years} under {root}"
        )

    return xr.concat(datasets, dim="init_time")
