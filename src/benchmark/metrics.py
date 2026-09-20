"""指标计算：纬度加权 RMSE / ACC / MAE / bias / 风矢量 RMSE / 技巧分（Phase 1）。

契约（口径与 WeatherBench 2 对齐）：
- RMSE：主指标，按变量 × 气压层 × lead time，纬度加权；
- ACC：距平相关系数，相对 30 年气候态；ACC < 0.6 视为无天气学价值（ECMWF 惯例）；
- 风矢量 RMSE = sqrt(RMSE_u² + RMSE_v²)；
- skill_score = 1 − RMSE_model / RMSE_baseline。
"""

from __future__ import annotations

import numpy as np


def latitude_weights(lat: np.ndarray) -> np.ndarray:
    """纬度权重，与 WeatherBench 2 一致。

    每个纬带权重正比于其面积（sinθ_upper − sinθ_lower），归一化到均值 1。
    """
    lat = np.asarray(lat, dtype=float)
    if lat.ndim != 1:
        raise ValueError("lat 必须是一维数组")
    # 以相邻格点中点为边界，两端按边缘半格处理
    bounds = np.empty(len(lat) + 1)
    bounds[1:-1] = (lat[:-1] + lat[1:]) / 2.0
    spacing = np.diff(lat)
    bounds[0] = lat[0] - spacing[0] / 2.0
    bounds[-1] = lat[-1] + spacing[-1] / 2.0
    weights = np.sin(np.deg2rad(bounds[1:])) - np.sin(np.deg2rad(bounds[:-1]))
    return weights / weights.mean()


def rmse(pred, truth, lat=None):
    """纬度加权 RMSE。"""
    raise NotImplementedError("metrics.rmse 将在 Phase 1 实现。")


def acc(pred, truth, climatology, lat=None):
    """距平相关系数（相对 30 年气候态）。"""
    raise NotImplementedError("metrics.acc 将在 Phase 1 实现。")


def mae(pred, truth, lat=None):
    """纬度加权平均绝对误差。"""
    raise NotImplementedError("metrics.mae 将在 Phase 1 实现。")


def bias(pred, truth, lat=None):
    """平均误差（系统性偏差）。"""
    raise NotImplementedError("metrics.bias 将在 Phase 1 实现。")


def wind_vector_rmse(rmse_u, rmse_v):
    """风矢量 RMSE = sqrt(RMSE_u² + RMSE_v²)。"""
    return float(np.sqrt(np.asarray(rmse_u) ** 2 + np.asarray(rmse_v) ** 2))


def skill_score(rmse_model, rmse_baseline):
    """技巧分 = 1 − RMSE_model / RMSE_baseline。"""
    return float(1.0 - np.asarray(rmse_model) / np.asarray(rmse_baseline))
