"""出榜：重建 leaderboard 与生成报告（Phase 2）。

契约：
- 同口径才可比：同一年份 / 区域 / 重网格 / 指标；
- leaderboard 记录 model_id + version + score_id + 配置 hash，配置变化产生新行、不覆盖；
- 排名维度：主指标（RMSE / ACC）按变量、时段、区域分列，支持过滤查看。
"""

from __future__ import annotations

from typing import Any, Dict


def rebuild_leaderboard(scores_dir: str, cfg: Dict[str, Any]):
    """聚合所有 score 生成 leaderboard.json 快照。"""
    raise NotImplementedError("report 将在 Phase 2 实现。")
