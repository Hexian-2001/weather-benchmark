"""Benchmark-scope config: loading, hashing, and path resolution.

``benchmark.yaml`` is the single definition of "one truth, one convention": every
score takes a hash of this config; any config change produces a new evaluation row
and never overwrites history (immutable archive).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import yaml

# repo root: src/benchmark/config.py -> parents[2] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = _REPO_ROOT / "config" / "benchmark.yaml"


def load_config(path: Path | str | None = None) -> Dict[str, Any]:
    """Load benchmark.yaml and expand ``{root}`` placeholders in ``storage``."""
    path = Path(path) if path is not None else DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_config_path"] = str(path)
    return resolve_storage(cfg)


def resolve_storage(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Replace the ``{root}`` placeholder in each ``storage.*`` entry."""
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
    """Canonical hash of the config (runtime fields excluded) — the evaluation fingerprint."""
    canonical = {k: v for k, v in cfg.items() if not k.startswith("_")}
    canonical.pop("storage", None)  # runtime paths don't participate in the fingerprint
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def start_year(cfg: Dict[str, Any]) -> int:
    """Evaluation start year (the hard unseen-year compliance threshold)."""
    return int(cfg["years"]["test"][0])
