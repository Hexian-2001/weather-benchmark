"""Metrics: latitude-weighted RMSE / ACC / MAE / bias / wind-vector RMSE / skill score (Phase 1).

Contract (aligned with WeatherBench 2):
- RMSE: primary, per variable × pressure level × lead time, latitude-weighted;
- ACC: anomaly correlation coefficient vs the 30-yr climatology; ACC < 0.6 = no synoptic
  skill (ECMWF convention);
- wind-vector RMSE = sqrt(RMSE_u² + RMSE_v²);
- skill_score = 1 − RMSE_model / RMSE_baseline.
"""

from __future__ import annotations

import numpy as np


def latitude_weights(lat: np.ndarray) -> np.ndarray:
    """Latitude weights, consistent with WeatherBench 2.

    Each latitude band is weighted by its area (sinθ_upper − sinθ_lower), normalized to mean 1.
    """
    lat = np.asarray(lat, dtype=float)
    if lat.ndim != 1:
        raise ValueError("lat must be a 1-D array")
    # use the midpoint between neighboring grid points as band edges, half-cell at both ends
    bounds = np.empty(len(lat) + 1)
    bounds[1:-1] = (lat[:-1] + lat[1:]) / 2.0
    spacing = np.diff(lat)
    bounds[0] = lat[0] - spacing[0] / 2.0
    bounds[-1] = lat[-1] + spacing[-1] / 2.0
    weights = np.sin(np.deg2rad(bounds[1:])) - np.sin(np.deg2rad(bounds[:-1]))
    return weights / weights.mean()


def rmse(pred, truth, lat=None):
    """Latitude-weighted RMSE."""
    raise NotImplementedError("metrics.rmse will be implemented in Phase 1.")


def acc(pred, truth, climatology, lat=None):
    """Anomaly correlation coefficient (vs the 30-yr climatology)."""
    raise NotImplementedError("metrics.acc will be implemented in Phase 1.")


def mae(pred, truth, lat=None):
    """Latitude-weighted mean absolute error."""
    raise NotImplementedError("metrics.mae will be implemented in Phase 1.")


def bias(pred, truth, lat=None):
    """Mean error (systematic bias)."""
    raise NotImplementedError("metrics.bias will be implemented in Phase 1.")


def wind_vector_rmse(rmse_u, rmse_v):
    """Wind-vector RMSE = sqrt(RMSE_u² + RMSE_v²)."""
    return float(np.sqrt(np.asarray(rmse_u) ** 2 + np.asarray(rmse_v) ** 2))


def skill_score(rmse_model, rmse_baseline):
    """Skill score = 1 − RMSE_model / RMSE_baseline."""
    return float(1.0 - np.asarray(rmse_model) / np.asarray(rmse_baseline))
