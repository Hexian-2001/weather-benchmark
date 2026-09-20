"""WeatherBench command-line entry point.

Subcommands:
    register    register a model card (schema + unseen-year compliance)
    verify      check truth coverage & prediction completeness (Phase 1)
    reforecast  orchestrate historical-initial-condition reruns (Phase 1, Slurm)
    score       score: ingest → regrid → metrics → write (Phase 1)
    report      rebuild leaderboard + generate report (Phase 2)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from . import config as config_mod
from . import registry


def _print_registration(reg: registry.Registration) -> int:
    print(f"model_id    : {reg.model_id}")
    print(f"schema      : {'PASS' if reg.schema_valid else 'FAIL'}")
    print(f"compliance  : {'PASS' if reg.compliant else 'FAIL'} (unseen-year)")
    print(f"reproducible: {'YES' if reg.reproducible else 'NO (internal-only trial)'}")
    if reg.issues:
        print("issues:")
        for issue in reg.issues:
            print(f"  - {issue}")
    if not reg.accepted:
        print("\n[REJECTED] registration rejected — fix schema / compliance issues first.")
        return 1
    print("\n[OK] registration accepted — ready for evaluation.")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    cfg = config_mod.load_config(args.config)
    year = args.start_year or config_mod.start_year(cfg)
    reg = registry.register(args.model_card, start_year=year)
    return _print_registration(reg)


def cmd_verify(args: argparse.Namespace) -> int:
    # Phase 1: check truth coverage and prediction completeness
    print(f"verify {args.model_id}: not implemented yet (Phase 1).")
    return 2


def cmd_reforecast(args: argparse.Namespace) -> int:
    # Phase 1: orchestrate historical-initial-condition reruns (Slurm)
    print(f"reforecast {args.model_id} --years {args.years}: not implemented yet (Phase 1).")
    return 2


def cmd_score(args: argparse.Namespace) -> int:
    # Phase 1: ingest → regrid → metrics → write
    print(f"score {args.model_id}: not implemented yet (Phase 1).")
    return 2


def cmd_report(args: argparse.Namespace) -> int:
    # Phase 2: rebuild leaderboard + generate report
    print("report: not implemented yet (Phase 2).")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="WeatherBench-MingYang-Tech — weather ML model benchmark platform",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="register a model card (schema + compliance)")
    p_reg.add_argument("model_card", type=Path, help="path to a model card YAML")
    p_reg.add_argument("--config", type=Path, default=None, help="path to benchmark.yaml")
    p_reg.add_argument("--start-year", type=int, default=None, help="evaluation start year (default from config)")
    p_reg.set_defaults(func=cmd_register)

    p_ver = sub.add_parser("verify", help="check truth coverage & prediction completeness")
    p_ver.add_argument("model_id")
    p_ver.set_defaults(func=cmd_verify)

    p_ref = sub.add_parser("reforecast", help="orchestrate historical-initial-condition reruns")
    p_ref.add_argument("model_id")
    p_ref.add_argument("--years", default="2023-2025")
    p_ref.set_defaults(func=cmd_reforecast)

    p_score = sub.add_parser("score", help="score a model")
    p_score.add_argument("model_id")
    p_score.set_defaults(func=cmd_score)

    p_rep = sub.add_parser("report", help="rebuild leaderboard + report")
    p_rep.set_defaults(func=cmd_report)

    return parser


def _reconfigure_stdout() -> None:
    """Force UTF-8 output (Windows consoles default to a legacy code page)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _reconfigure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
