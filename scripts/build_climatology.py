#!/usr/bin/env python
"""构建 30 年逐日气候态（默认 1991–2020），作为 ACC 与气候态基线的参照。

用法（在 Pawsey 上，数据已就位后）：
    python scripts/build_climatology.py \
        --era5 /scratch/pawsey0115/hwang4/datasets/era5.zarr \
        --out  /scratch/pawsey0115/hwang4/work_projects/weather-benchmark/data/climatology/climatology_1991_2020.nc \
        --variables 2m_temperature mean_sea_level_pressure geopotential \
        --period 1991 2020 --smooth 5

说明：
- 按 day-of-year 求多年平均得到 365 天逐日气候态；
- ``--smooth N`` 对 day-of-year 做 N 天滑动平均，消除采样噪声（闰日 2/29 归入 day 60）；
- 预计算并缓存，打分阶段只读缓存、只做纯计算。
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="构建 30 年逐日气候态")
    p.add_argument("--era5", required=True, type=Path, help="ERA5 数据路径（zarr/netcdf）")
    p.add_argument("--out", required=True, type=Path, help="输出 NetCDF 路径")
    p.add_argument("--variables", nargs="+", required=True, help="参与气候态的变量")
    p.add_argument("--period", nargs=2, type=int, default=[1991, 2020], help="气候态年份 [起 止]")
    p.add_argument("--smooth", type=int, default=5, help="day-of-year 滑动平均窗宽（奇数）")
    p.add_argument("--lat", nargs=2, type=float, default=[15.0, 55.0])
    p.add_argument("--lon", nargs=2, type=float, default=[70.0, 140.0])
    return p.parse_args()


def main() -> int:
    args = parse_args()
    start, end = args.period
    print(f"[climatology] 读取 ERA5: {args.era5}")

    ds = xr.open_zarr(args.era5) if str(args.era5).endswith(".zarr") else xr.open_dataset(args.era5)

    # 选年份 + 区域 + 变量
    ds = ds.sel(time=slice(f"{start}-01-01", f"{end}-12-31"))
    ds = ds.sel(lat=slice(*sorted(args.lat)), lon=slice(*sorted(args.lon)))
    ds = ds[[v for v in args.variables if v in ds]]

    # 逐日气候态：先取日均，再对 day-of-year 多年平均
    daily = ds.resample(time="1D").mean("time")
    doy = daily["time.dayofyear"]
    climatology = daily.groupby(doy).mean("time")

    # 闰日 2/29 归入 day 60，保持 365 天
    climatology = climatology.sel(dayofyear=climatology.dayofyear != 366)

    if args.smooth and args.smooth > 1:
        climatology = climatology.rolling(dayofyear=args.smooth, center=True, min_periods=1).mean()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    climatology.to_netcdf(args.out)
    print(f"[climatology] 已写出: {args.out}  (变量: {list(climatology.data_vars)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
