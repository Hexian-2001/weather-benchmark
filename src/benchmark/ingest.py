"""Data ingestion: read reforecast predictions into a canonical Dataset (Phase 1).

Contract:
- The benchmark **defines** the canonical reforecast format (aligned with WeatherBench 2 /
  ERA5 conventions); the reforecast step writes it and this module reads it. There is no
  external ``prediction_store`` to adapt — the Aurora/GraphCast rollout produces an in-memory
  ``Batch``, so the reforecast step serializes it into the format described here.
- Layout: one netCDF (``.nc``) or zarr (``.zarr``) per initialization time under
  ``results/<model_id>/predictions/``. Each file has dims ``(lead_time[, level], lat, lon)``,
  a scalar ``init_time`` coordinate, and a ``lead_time`` coordinate in hours.
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

# Aurora ``Batch`` short keys → WeatherBench 2 / ERA5 long names.
VARIABLE_ALIASES: Dict[str, str] = {
    # surface
    "2t": "2m_temperature",
    "10u": "10m_u_component_of_wind",
    "10v": "10m_v_component_of_wind",
    "msl": "mean_sea_level_pressure",
    # atmospheric
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


def _init_time(ds: xr.Dataset, path: Path) -> pd.Timestamp:
    """Resolve the initialization time of one prediction file.

    Preference order: an ``init_time`` / ``forecast_reference_time`` coordinate, then the
    filename (``YYYYMMDDHH``, ``YYYY-MM-DDTHH`` or ``YYYYMMDD``).
    """
    for name in ("init_time", "forecast_reference_time", "analysis_time"):
        if name in ds.coords and ds[name].size == 1:
            return pd.Timestamp(np.atleast_1d(ds[name].values)[0])

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
    """List prediction files (``.nc`` / ``.zarr``) under the predictions root."""
    if not root.is_dir():
        raise FileNotFoundError(f"predictions root not found: {root}")
    files = sorted(root.glob("*.nc")) + sorted(root.glob("*.zarr"))
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
    root = Path(storage["results_dir"]) / model_id / "predictions"
    datasets = []
    for path in _discover_files(root):
        ds = canonicalize_variables(normalize_spatial(xr.open_dataset(path)))
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
