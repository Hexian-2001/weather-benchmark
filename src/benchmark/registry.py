"""模型卡注册：schema 校验 + unseen-year 合规 + 可复现性标记。

模型卡是进入 benchmark 的"入场券"：
- 结构必须符合 ``registry/schema/model_card.schema.json``；
- ``attestation.training_end_year`` / ``finetune_end_year`` 必须严格小于测评起始年；
- 缺 ``base_checkpoint_hash`` / ``code_ref`` 则标记为"不可复现"，只允许内部临时测评。
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _REPO_ROOT / "registry" / "schema" / "model_card.schema.json"
MODELS_DIR = _REPO_ROOT / "registry" / "models"


@dataclass
class Registration:
    """一次注册/校验的结果。"""

    model_id: str
    schema_valid: bool
    compliant: bool
    reproducible: bool
    issues: List[str] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.schema_valid and self.compliant


def load_schema() -> Dict[str, Any]:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _stringify(obj: Any) -> Any:
    """把 PyYAML 自动解析出的 date/datetime 还原为 ISO 字符串（JSON Schema 要求 string）。"""
    if isinstance(obj, (_dt.datetime, _dt.date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _stringify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify(v) for v in obj]
    return obj


def load_model_card(path: Path | str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return _stringify(yaml.safe_load(fh))


def validate_schema(card: Dict[str, Any], schema: Dict[str, Any] | None = None) -> List[str]:
    """返回 schema 违规列表；空列表表示结构合法。"""
    schema = schema or load_schema()
    errors = []
    for err in sorted(jsonschema.Draft7Validator(schema).iter_errors(card), key=str):
        errors.append(f"{'.'.join(str(p) for p in err.path) or '(root)'}: {err.message}")
    return errors


def check_compliance(card: Dict[str, Any], start_year: int) -> List[str]:
    """unseen-year 合规校验：训练/微调截止年必须 < 测评起始年。"""
    issues = []
    attest = card.get("attestation", {})
    for key in ("training_end_year", "finetune_end_year"):
        end = attest.get(key)
        if end is None:
            issues.append(f"attestation.{key} 缺失")
        elif int(end) >= start_year:
            issues.append(
                f"attestation.{key}={end} 违反 unseen-year（必须 < {start_year}）"
            )
    return issues


def check_reproducibility(card: Dict[str, Any]) -> List[str]:
    """可复现性标记：缺 checkpoint 哈希或代码引用则降级为'内部临时测评'。"""
    issues = []
    training = card.get("training", {})
    repro = card.get("reproducibility", {})
    if not training.get("base_checkpoint_hash") or "TODO" in str(training.get("base_checkpoint_hash")):
        issues.append("缺 base_checkpoint_hash，标记为'不可复现'")
    if not repro.get("code_ref") or "TODO" in str(repro.get("code_ref")):
        issues.append("缺 code_ref，标记为'不可复现'")
    return issues


def register(path: Path | str, start_year: int) -> Registration:
    """加载并校验一张模型卡，返回 Registration 汇总。"""
    card = load_model_card(path)
    schema_issues = validate_schema(card)
    compliance_issues = check_compliance(card, start_year) if not schema_issues else []
    repro_issues = check_reproducibility(card)

    issues = schema_issues + compliance_issues + repro_issues
    return Registration(
        model_id=card.get("model_id", "<missing>"),
        schema_valid=not schema_issues,
        compliant=not compliance_issues,
        reproducible=not repro_issues,
        issues=issues,
    )
