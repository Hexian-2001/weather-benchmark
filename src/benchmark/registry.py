"""Model-card registration: schema validation + unseen-year compliance + reproducibility flag.

The model card is the entry ticket to the benchmark:
- its structure must match ``registry/schema/model_card.schema.json``;
- ``attestation.training_end_year`` / ``finetune_end_year`` must be strictly earlier
  than the evaluation start year;
- missing ``base_checkpoint_hash`` / ``code_ref`` flags the card as non-reproducible,
  allowing internal trial evaluation only.
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
    """Summary of one registration/validation run."""

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
    """Convert PyYAML's auto-parsed date/datetime back to ISO strings (JSON Schema wants strings)."""
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
    """Return schema violations; an empty list means the structure is valid."""
    schema = schema or load_schema()
    errors = []
    for err in sorted(jsonschema.Draft7Validator(schema).iter_errors(card), key=str):
        errors.append(f"{'.'.join(str(p) for p in err.path) or '(root)'}: {err.message}")
    return errors


def check_compliance(card: Dict[str, Any], start_year: int) -> List[str]:
    """Unseen-year compliance: training/fine-tune end years must be < the evaluation start year."""
    issues = []
    attest = card.get("attestation", {})
    for key in ("training_end_year", "finetune_end_year"):
        end = attest.get(key)
        if end is None:
            issues.append(f"attestation.{key} is missing")
        elif int(end) >= start_year:
            issues.append(
                f"attestation.{key}={end} violates unseen-year (must be < {start_year})"
            )
    return issues


def check_reproducibility(card: Dict[str, Any]) -> List[str]:
    """Reproducibility flag: missing checkpoint hash or code ref → internal-trial only."""
    issues = []
    training = card.get("training", {})
    repro = card.get("reproducibility", {})
    if not training.get("base_checkpoint_hash") or "TODO" in str(training.get("base_checkpoint_hash")):
        issues.append("missing base_checkpoint_hash (flagged non-reproducible)")
    if not repro.get("code_ref") or "TODO" in str(repro.get("code_ref")):
        issues.append("missing code_ref (flagged non-reproducible)")
    return issues


def register(path: Path | str, start_year: int) -> Registration:
    """Load and validate a model card, returning a Registration summary."""
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
