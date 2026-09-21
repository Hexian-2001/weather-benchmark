"""Download ERA5 initial conditions (IC) for model inference, from the Copernicus CDS.

The benchmark runs the *deployed* Aurora (``0.25-finetuned``) and GraphCast
(``operational``) variants. Both are global 0.25-degree models with a 6-hour step and a
13-level pressure stack, and their conditioning window is two steps (T-6h, T). Their
operational IC is IFS HRES ``fc0`` via ECMWF Open Data — which is not available
retroactively for 2024 (Open Data is not archived, and MARS access is gated). The free,
IFS-family substitute is **ERA5 0.25 deg** (same grid, same short variable names, same
levels), which is the standard benchmark convention (GraphCast is trained and evaluated
on ERA5).

What this fetches, at 00/06/12/18 UTC (the 4 cycles/day the models run, which also cover
the T-6h history for the 00/12 UTC benchmark init times):

  * ERA5 single-levels   (0.25 deg, 6-hourly) -> surface IC (2m_temperature, 10m u/v, MSLP)
  * ERA5 pressure-levels (0.25 deg, 6-hourly) -> upper-air IC (geopotential / temperature /
                                                  u / v / specific_humidity at the 13 WB levels)

Static fields (``z``/``lsm``/``slt``) are NOT downloaded: they are fixed, model-specific
and already present on Pawsey (``aurora-0.25-static.pickle``, GraphCast ``static`` file).

The download is GLOBAL (no ``area`` restriction) because the models ingest the full
721x1440 state. This is ~110-140 GB per year at 13 levels (see ``docs/benchmark_plan.md``);
the truth download, by contrast, is China-boxed because scoring is regional.

Chunking / resumability / output naming mirror ``scripts/download_truth.py``: day-window
chunks to stay under the CDS cost limit, ``.part`` + atomic rename, and a SHA-256 sidecar
so a re-run resumes where it stopped.

Requires a valid ``~/.cdsapirc`` and ``cdsapi`` installed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import time
import zipfile

import cdsapi

# 4 analysis cycles/day: the models' 2-step conditioning window (T-6h, T) at the
# benchmark 00/12 UTC init times needs 00/06/12/18 UTC fields.
HOURS = ["00:00", "06:00", "12:00", "18:00"]
MONTHS = [f"{m:02d}" for m in range(1, 13)]

# The 13 pressure levels shared by the deployed Aurora and GraphCast variants.
PRESSURE_LEVELS = [
    "50", "100", "150", "200", "250", "300", "400",
    "500", "600", "700", "850", "925", "1000",
]

REQUESTS = {
    "era5-ic-surface": {
        "dataset": "reanalysis-era5-single-levels",
        "variable": [
            "2m_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "mean_sea_level_pressure",
        ],
        "grid": [0.25, 0.25],
        "days_per_request": 31,  # 4 fields x 4 cycles/day x 31 days is within the cost limit
    },
    "era5-ic-pressure": {
        "dataset": "reanalysis-era5-pressure-levels",
        "variable": [
            "geopotential",
            "temperature",
            "u_component_of_wind",
            "v_component_of_wind",
            "specific_humidity",
        ],
        "pressure_level": PRESSURE_LEVELS,
        "grid": [0.25, 0.25],
        "days_per_request": 7,   # 5 fields x 13 levels x 4 cycles/day; chunk to 7 days
    },
}


def build_request(spec: dict, year: int, month: str, days: list[str]) -> dict:
    # No ``area`` key -> global (the models ingest the full 721x1440 state).
    request = {
        "product_type": "reanalysis",
        "variable": spec["variable"],
        "year": str(year),
        "month": month,
        "day": days,
        "time": HOURS,
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


def _retrieve(client, dataset: str, request: dict, target: str, attempts: int = 6) -> None:
    """Retrieve with retry/backoff so transient CDS throttling (parallel jobs) is non-fatal.

    A genuine cost-limit refusal is not retried forever, but parallel month-jobs can hit
    transient "too many requests"/5xx/network errors; those clear as other requests finish.
    """
    delay = 30
    for attempt in range(1, attempts + 1):
        try:
            client.retrieve(dataset, request, target)
            return
        except Exception as exc:
            if attempt == attempts:
                raise
            print(f"  retry {attempt}/{attempts - 1} in {delay}s: {exc}", flush=True)
            time.sleep(delay)
            delay *= 2


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
    _retrieve(client, spec["dataset"], build_request(spec, year, month, days), tmp)
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
        "--outdir", default="data/ic",
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
