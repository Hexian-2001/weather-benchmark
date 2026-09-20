"""测评范围配置的加载、哈希与路径解析。

`benchmark.yaml` 是"单一真值、同口径对比"的唯一定义：任何一次 score 都对该配置
取哈希，配置变化即产生新的测评行，不覆盖历史（不可变存档原则）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import yaml

# 仓库根目录：src/benchmark/config.py -> parents[2] = 仓库根
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = _REPO_ROOT / "config" / "benchmark.yaml"


def load_config(path: Path | str | None = None) -> Dict[str, Any]:
    """加载 benchmark.yaml 并展开 storage 中的 {root} 占位符。"""
    path = Path(path) if path is not None else DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_config_path"] = str(path)
    return resolve_storage(cfg)


def resolve_storage(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """把 storage.* 里的 ``{root}`` 占位符替换为实际路径。"""
    storage = cfg.get("storage", {})
    root = storage.get("root", "")
    resolved = {}
    for key, value in storage.items():
        if isinstance(value, str):
            resolved[key] = value.format(root=root)
        else:
            resolved[key] = value
    cfg["storage"] = resolved
    return cfg


def config_hash(cfg: Dict[str, Any]) -> str:
    """对配置取规范哈希（去路径等运行时字段），作为测评口径的指纹。"""
    canonical = {k: v for k, v in cfg.items() if not k.startswith("_")}
    canonical.pop("storage", None)  # 运行时路径不参与口径指纹
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def start_year(cfg: Dict[str, Any]) -> int:
    """测评起始年（unseen-year 合规的硬阈值）。"""
    return int(cfg["years"]["test"][0])
