"""Metrics: latitude-weighted RMSE / ACC / MAE / bias / wind-vector RMSE / skill score.

Contract (aligned with WeatherBench 2):
- RMSE: primary, per variable × pressure level × lead time, latitude-weighted;
- ACC: anomaly correlation coefficient vs the 30-yr climatology; ACC < 0.6 = no synoptic
  skill (ECMWF convention);
- wind-vector RMSE = sqrt(RMSE_u² + RMSE_v²);
- skill_score = 1 − RMSE_model / RMSE_baseline.

``pred`` / ``truth`` (and ``climatology`` for ACC) are xarray DataArrays with ``lat``
and ``lon`` dims; the functions reduce those two dims and preserve any leading dims
(e.g. ``lead_time``, ``level``). ``lat`` (degrees, any monotonic order) defaults to
``pred["lat"]``.
"""

from __future__ import annotations

import numpy as np
import xarray as xr


def latitude_weights(lat: np.ndarray) -> np.ndarray:
    """Latitude weights = cos(latitude), normalized to mean 1 (WeatherBench 2 convention).

    Pole cells get weight 0 (a point has zero area); mid-latitude cells are positive.
    Works for ascending (south-to-north) or descending (north-to-south) latitude.
    """
    lat = np.asarray(lat, dtype=float)
    if lat.ndim != 1:
        raise ValueError("lat must be a 1-D array")
    weights = np.cos(np.deg2rad(lat))
    return weights / weights.mean()


def _weights(pred, lat):
    """Build a latitude-weight DataArray aligned to ``pred``'s ``lat`` coordinate."""
    if lat is None:
        lat = pred["lat"]
    lat_vals = np.asarray(lat, dtype=float)
    return xr.DataArray(latitude_weights(lat_vals), dims="lat", coords={"lat": lat_vals})


def rmse(pred, truth, lat=None):
    """Latitude-weighted root-mean-square error, reduced over (lat, lon)."""
    w = _weights(pred, lat)
    return np.sqrt(((pred - truth) ** 2).weighted(w).mean(("lat", "lon")))


def acc(pred, truth, climatology, lat=None):
    """Anomaly correlation coefficient vs the 30-yr climatology, reduced over (lat, lon).

    ``climatology`` must already be aligned/broadcast to ``pred``/``truth``.
    """
    w = _weights(pred, lat)
    p = pred - climatology
    t = truth - climatology
    numer = (p * t).weighted(w).sum(("lat", "lon"))
    denom = np.sqrt((p ** 2).weighted(w).sum(("lat", "lon")) * (t ** 2).weighted(w).sum(("lat", "lon")))
    return xr.where(denom > 0, numer / denom, float("nan"))


def mae(pred, truth, lat=None):
    """Latitude-weighted mean absolute error, reduced over (lat, lon)."""
    w = _weights(pred, lat)
    return np.abs(pred - truth).weighted(w).mean(("lat", "lon"))


def bias(pred, truth, lat=None):
    """Latitude-weighted mean error (systematic bias), reduced over (lat, lon)."""
    w = _weights(pred, lat)
    return (pred - truth).weighted(w).mean(("lat", "lon"))


def wind_vector_rmse(rmse_u, rmse_v):
    """Wind-vector RMSE = sqrt(RMSE_u² + RMSE_v²)."""
    return float(np.sqrt(np.asarray(rmse_u) ** 2 + np.asarray(rmse_v) ** 2))


def skill_score(rmse_model, rmse_baseline):
    """Skill score = 1 − RMSE_model / RMSE_baseline."""
    return float(1.0 - np.asarray(rmse_model) / np.asarray(rmse_baseline))
