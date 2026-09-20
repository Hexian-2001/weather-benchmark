"""重网格：把原生分辨率统一到 0.25° 通用对比网格（Phase 1）。

契约：
- 0.1° 模型：原生分辨率打一次分 + 一阶保守重映射到 0.25° 再打一次；
- 重映射采用一阶保守（与 WeatherBench 2 一致）；
- 真值 / 气候态同样统一重网格后落盘缓存。
"""

from __future__ import annotations

from typing import Any, Dict


def conservative_regrid(ds, target_grid_deg: float = 0.25, method: str = "conservative"):
    """一阶保守重映射到目标网格。"""
    raise NotImplementedError("regrid 将在 Phase 1 实现：一阶保守重映射。")
