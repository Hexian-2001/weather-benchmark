#!/usr/bin/env python
"""Build the 30-yr daily climatology (default 1991–2020) for ACC and the climatology baseline.

Usage (on Pawsey, after data is in place):
    python scripts/build_climatology.py \
        --era5 /scratch/pawsey0115/hwang4/datasets/era5.zarr \
        --out  /scratch/pawsey0115/hwang4/work_projects/weather-benchmark/data/climatology/climatology_1991_2020.nc \
        --variables 2m_temperature mean_sea_level_pressure geopotential \
        --period 1991 2020 --smooth 5

Notes:
- averages across years per day-of-year → a 365-day daily climatology;
- ``--smooth N`` applies an N-day sliding mean over day-of-year to remove sampling noise
  (leap day 2/29 is folded into day 60);
- precomputed and cached; the scoring stage only reads the cache.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import xarray as xr

# allow running this script standalone without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from benchmark.climatology import build_daily_climatology  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="build the 30-yr daily climatology")
    p.add_argument("--era5", required=True, type=Path, help="ERA5 data path (zarr/netcdf)")
    p.add_argument("--out", required=True, type=Path, help="output NetCDF path")
    p.add_argument("--variables", nargs="+", required=True, help="variables included in the climatology")
    p.add_argument("--period", nargs=2, type=int, default=[1991, 2020], help="climatology years [start end]")
    p.add_argument("--smooth", type=int, default=5, help="day-of-year sliding-mean window (odd)")
    p.add_argument("--lat", nargs=2, type=float, default=[15.0, 55.0])
    p.add_argument("--lon", nargs=2, type=float, default=[70.0, 140.0])
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[climatology] reading ERA5: {args.era5}")

    ds = xr.open_zarr(args.era5) if str(args.era5).endswith(".zarr") else xr.open_dataset(args.era5)

    # select region here; the module handles year/variable selection and the reduction
    ds = ds.sel(lat=slice(*sorted(args.lat)), lon=slice(*sorted(args.lon)))

    climatology = build_daily_climatology(
        ds, period=tuple(args.period), variables=args.variables, smooth=args.smooth
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    climatology.to_netcdf(args.out)
    print(f"[climatology] written: {args.out}  (variables: {list(climatology.data_vars)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
