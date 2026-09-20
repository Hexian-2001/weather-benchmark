"""Unit tests for benchmark.metrics."""

import numpy as np
import xarray as xr

from benchmark import metrics


def _field(lat=None, lon=None, seed=0):
    lat = np.linspace(-45.0, 45.0, 8) if lat is None else lat
    lon = np.linspace(0.0, 30.0, 12) if lon is None else lon
    rng = np.random.default_rng(seed)
    return xr.DataArray(
        rng.normal(size=(len(lat), len(lon))),
        dims=("lat", "lon"),
        coords={"lat": lat, "lon": lon},
    )


def test_latitude_weights_mean_one():
    w = metrics.latitude_weights(np.linspace(-89.0, 89.0, 37))
    assert np.isclose(w.mean(), 1.0)
    assert (w > 0).all()


def test_latitude_weights_pole_is_zero():
    # the pole is a point (zero area), so its weight is zero (up to float precision)
    w = metrics.latitude_weights(np.array([-90.0, 0.0, 90.0]))
    assert w[0] < 1e-12
    assert w[-1] < 1e-12
    assert np.isclose(w.mean(), 1.0)


def test_latitude_weights_descending_positive():
    # ERA5 latitude is north-to-south (descending); weights must stay positive
    w = metrics.latitude_weights(np.linspace(89.0, -89.0, 37))
    assert (w > 0).all()
    assert np.isclose(w.mean(), 1.0)


def test_rmse_constant_error():
    truth = _field()
    pred = truth + 2.0
    assert np.isclose(float(metrics.rmse(pred, truth)), 2.0)


def test_rmse_zero_when_identical():
    truth = _field()
    assert np.isclose(float(metrics.rmse(truth, truth)), 0.0)


def test_mae():
    truth = _field()
    pred = truth + 3.0
    assert np.isclose(float(metrics.mae(pred, truth)), 3.0)


def test_bias():
    truth = _field()
    pred = truth + 3.0
    assert np.isclose(float(metrics.bias(pred, truth)), 3.0)


def test_acc_perfect_positive():
    anomaly = _field()
    clim = xr.zeros_like(anomaly)
    truth = clim + anomaly
    pred = clim + 2.0 * anomaly
    assert np.isclose(float(metrics.acc(pred, truth, clim)), 1.0)


def test_acc_perfect_negative():
    anomaly = _field()
    clim = xr.zeros_like(anomaly)
    truth = clim + anomaly
    pred = clim - anomaly
    assert np.isclose(float(metrics.acc(pred, truth, clim)), -1.0)


def test_acc_zero_variance_is_nan():
    base = _field()
    assert np.isnan(float(metrics.acc(base, base, base)))


def test_wind_vector_rmse():
    assert np.isclose(metrics.wind_vector_rmse(3.0, 4.0), 5.0)


def test_skill_score():
    assert np.isclose(metrics.skill_score(2.0, 4.0), 0.5)
