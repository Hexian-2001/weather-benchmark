"""数据摄取：把模型回跑产物读入统一结构（Phase 1）。

契约：
- 复用 ``foehn_core.prediction_store`` 的统一预测格式，不另起炉灶；
- 回跑产物位于 ``results/<model>/<variant>/<init>Z/predictions/``；
- 输出标准化的 xarray.Dataset：维度 (init_time, lead_time, variable[, level], lat, lon)。
"""

from __future__ import annotations

from typing import Any, Dict


def load_predictions(model_id: str, years: list[int], storage: Dict[str, Any]):
    """读取某模型在给定年份的回跑预测，返回标准化 Dataset。"""
    raise NotImplementedError("ingest 将在 Phase 1 实现：对接 prediction_store 统一格式。")
