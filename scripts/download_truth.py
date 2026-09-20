"""Download benchmark ground truth from the Copernicus Climate Data Store (CDS).

Truth sources for the WeatherBench-MingYang-Tech benchmark:

  * ERA5 single-levels    (0.25 deg, hourly) -> surface truth (2m_temperature, 10m u/v, MSLP)
  * ERA5 pressure-levels  (0.25 deg, hourly) -> upper-air truth (geopotential / temperature /
                                                 u / v / specific_humidity at 250/500/850 hPa)
  * ERA5-Land             (0.1  deg, hourly) -> 0.1 deg surface truth (surface-only)

Why these and not IFS HRES ``fc0`` (0.1 deg): the HRES analysis is distributed through ECMWF
MARS (licensed access), not the free CDS, and it is produced 6-hourly (00/06/12/18 UTC) so it
cannot score 1-hourly predictions anyway. ERA5-Land is the only freely available 0.1 deg,
hourly product, and it is surface-only (no upper-air, no MSLP). See docs/benchmark_plan.md
section 5.

Chunking: the CDS enforces a per-request "cost" limit, so each dataset is split into
day-windows (``days_per_request``). Pressure levels (15 fields) and ERA5-Land (0.1 deg grid,
~16x the points of 0.25 deg) must be chunked finer than single-levels. Each window is written
as one shard; a full-month window keeps the ``<name>_<year><month>.nc`` name, a partial window
gets a ``_<startday>`` suffix.

Resumability: each shard is written to a ``.part`` temp file, atomically renamed on success,
and a SHA-256 sidecar (``.sha256``) is recorded. Any shard that already exists and matches its
checksum is skipped, so a re-run resumes where it stopped.

Region: the China evaluation box (15-55 N, 70-140 E) plus a 1 deg margin for regridding edges.

Requires a valid ``~/.cdsapirc`` (CDS API key) and ``cdsapi`` installed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import zipfile

import cdsapi

# CDS `area` is [North, West, South, East]; 1 deg margin around the China box.
AREA = [55, 70, 15, 140]

HOURS = [f"{h:02d}:00" for h in range(24)]
MONTHS = [f"{m:02d}" for m in range(1, 13)]

REQUESTS = {
    "era5-0p25-surface": {
        "dataset": "reanalysis-era5-single-levels",
        "variable": [
            "2m_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "mean_sea_level_pressure",
        ],
        "grid": [0.25, 0.25],
        "days_per_request": 31,  # full month is within the CDS cost limit (verified)
    },
    "era5-0p25-pressure": {
        "dataset": "reanalysis-era5-pressure-levels",
        "variable": [
            "geopotential",
            "temperature",
            "u_component_of_wind",
            "v_component_of_wind",
            "specific_humidity",
        ],
        "pressure_level": ["250", "500", "850"],
        "grid": [0.25, 0.25],
        "days_per_request": 7,   # 15 fields x 24h x 31d exceeded the limit; chunk to 7 days
    },
    "era5-land-0p1-surface": {
        "dataset": "reanalysis-era5-land",
        "variable": [
            "2m_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "surface_pressure",
        ],
        # Native 0.1 deg grid; no `grid` key (ERA5-Land is not regriddable via that key).
        "days_per_request": 4,   # 0.1 deg ~ 16x the points of 0.25 deg; chunk to 4 days
    },
}


def build_request(spec: dict, year: int, month: str, days: list[str]) -> dict:
    request = {
        "product_type": "reanalysis",
        "variable": spec["variable"],
        "year": str(year),
        "month": month,
        "day": days,
        "time": HOURS,
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    if "grid" in spec:
        request["grid"] = spec["grid"]
    if "pressure_level" in spec:
        request["pressure_level"] = spec["pressure_level"]
    return request


def day_windows(days_per_request: int) -> list[list[str]]:
    """Split a 31-day month into day lists of at most ``days_per_request`` days each."""
    windows = []
    start = 1
    while start <= 31:
        end = min(start + days_per_request - 1, 31)
        windows.append([f"{d:02d}" for d in range(start, end + 1)])
        start = end + 1
    return windows


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unzip_if_needed(path: str) -> None:
    """If ``path`` is a zip archive (CDS may ignore ``unarchived``), extract the first .nc."""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if head != b"PK\x03\x04":
        return
    with zipfile.ZipFile(path) as zf:
        member = next(n for n in zf.namelist() if n.endswith(".nc"))
        data = zf.read(member)
    with open(path, "wb") as fh:
        fh.write(data)


def is_complete(nc_path: str, sha_path: str) -> bool:
    if not (os.path.isfile(nc_path) and os.path.isfile(sha_path)):
        return False
    with open(sha_path) as fh:
        expected = fh.read().strip().split()[0]
    return sha256_of(nc_path) == expected


def download_window(client, name: str, spec: dict, year: int, month: str,
                    days: list[str], outdir: str) -> None:
    out_dir = os.path.join(outdir, name, str(year))
    os.makedirs(out_dir, exist_ok=True)
    suffix = "" if len(days) == 31 else f"_{days[0]}"
    nc_path = os.path.join(out_dir, f"{name}_{year}{month}{suffix}.nc")
    sha_path = nc_path + ".sha256"
    label = f"{name} {year}-{month} days {days[0]}..{days[-1]}"
    if is_complete(nc_path, sha_path):
        print(f"skip  {label} (already complete)", flush=True)
        return

    tmp = nc_path + ".part"
    if os.path.exists(tmp):
        os.remove(tmp)

    print(f"request {label} ...", flush=True)
    client.retrieve(spec["dataset"], build_request(spec, year, month, days), tmp)
    _unzip_if_needed(tmp)

    os.replace(tmp, nc_path)
    digest = sha256_of(nc_path)
    with open(sha_path, "w") as fh:
        fh.write(f"{digest}  {os.path.basename(nc_path)}\n")
    print(f"done  {label}  sha256={digest[:16]}", flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="year to download, e.g. 2024")
    parser.add_argument(
        "--outdir", default="data/truth",
        help="output root; shards land under <outdir>/<dataset>/<year>/",
    )
    parser.add_argument(
        "--datasets", nargs="*", default=["all"],
        choices=list(REQUESTS) + ["all"],
        help="which datasets to fetch (default: all)",
    )
    parser.add_argument(
        "--months", nargs="*", default=MONTHS,
        help="months to fetch, e.g. 01 02 (default: all 12)",
    )
    args = parser.parse_args(argv)

    names = list(REQUESTS) if "all" in args.datasets else args.datasets
    client = cdsapi.Client()

    for name in names:
        spec = REQUESTS[name]
        for month in args.months:
            for days in day_windows(spec["days_per_request"]):
                download_window(client, name, spec, args.year, month, days, args.outdir)

    print("all requested downloads complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
