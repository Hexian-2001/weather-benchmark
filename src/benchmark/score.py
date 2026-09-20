"""打分：把 (预测, 真值, 气候态, 配置) 映射为指标（Phase 1）。

契约：
- 打分是**纯函数**，可重放：同输入必得同输出；
- 产出 metric cube（NetCDF，维度 metric × var × level × lead × region）+ summary.json；
- 按 ``score_id`` 原子落盘，不覆盖历史。
"""

from __future__ import annotations

from typing import Any, Dict


def score(pred, truth, climatology, cfg: Dict[str, Any]):
    """对一组回跑结果算指标，返回 (metric_cube, summary)。"""
    raise NotImplementedError("score 将在 Phase 1 实现：ingest → regrid → metrics → 落盘。")
