"""气候态：30 年逐日气候态（1991–2020），作为 ACC 与气候态基线的参照（Phase 1）。

契约：
- 输入 ERA5，按 day-of-year 求多年平均，得到 365 天逐日气候态；
- 预计算并缓存，打分阶段只做纯计算；
- 具体构建脚本见 ``scripts/build_climatology.py``。
"""

from __future__ import annotations

from typing import Any, Dict


def build_daily_climatology(ds, period: tuple[int, int], variables: list[str]):
    """由 ERA5 逐时数据构建逐日气候态。"""
    raise NotImplementedError("climatology 将在 Phase 1 实现；脚本见 scripts/build_climatology.py")
