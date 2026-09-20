"""Regrid: bring native resolution onto the 0.25° common comparison grid.

Contract:
- 0.1° models: scored once at native resolution, then once after first-order
  conservative remapping to 0.25°;
- remapping is first-order conservative (consistent with WeatherBench 2);
- truth / climatology are likewise regridded once and cached.

Backend: ``xarray-regrid`` (lightweight, no ESMF). Install via
``pip install xarray-regrid``.
"""

from __future__ import annotations


def conservative_regrid(ds, target_grid_deg: float = 0.25, method: str = "conservative"):
    """First-order conservative remapping onto a regular ``target_grid_deg`` grid.

    ``ds`` must have 1-D ``lat`` and ``lon`` coordinates (a regular grid). The target
    grid spans the source's own extent and the output is returned on ascending
    (south-to-north) latitude.

    Note: when ``target_grid_deg`` is coarser than the source, the outermost target
    cells may extend beyond the source's half-cells and become NaN. Regrid a padded
    domain and subset afterward (or pass a source with a half-cell margin) to avoid it.
    """
    try:
        from xarray_regrid import Grid, Regridder
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "conservative_regrid requires the 'xarray-regrid' package "
            "(pip install xarray-regrid)"
        ) from exc

    lat = ds["lat"].values
    lon = ds["lon"].values
    grid = Grid(
        north=float(lat.max()),
        south=float(lat.min()),
        east=float(lon.max()),
        west=float(lon.min()),
        resolution_lat=target_grid_deg,
        resolution_lon=target_grid_deg,
    )
    target = grid.create_regridding_dataset(lat_name="lat", lon_name="lon")

    regridder = Regridder(ds)
    if method == "conservative":
        return regridder.conservative(target)
    if method == "linear":
        return regridder.linear(target)
    raise ValueError(f"unsupported regrid method: {method!r}")
