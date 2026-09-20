"""WeatherBench 命令行入口。

子命令：
    register    注册模型卡（schema + unseen-year 合规校验）
    verify      校验真值覆盖与预测文件完整性（Phase 1）
    reforecast  编排历史初始场回跑（Phase 1，Slurm）
    score       打分：ingest → regrid → metrics → 落盘（Phase 1）
    report      重建 leaderboard + 生成报告（Phase 2）
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
    print(f"schema      : {'通过' if reg.schema_valid else '不通过'}")
    print(f"合规(unseen): {'通过' if reg.compliant else '不通过'}")
    print(f"可复现      : {'是' if reg.reproducible else '否（仅内部临时测评）'}")
    if reg.issues:
        print("问题清单:")
        for issue in reg.issues:
            print(f"  - {issue}")
    if not reg.accepted:
        print("\n[REJECTED] 注册被拒绝：先修正 schema / 合规问题。")
        return 1
    print("\n[OK] 注册通过，可进入测评。")
    return 0


def cmd_register(args: argparse.Namespace) -> int:
    cfg = config_mod.load_config(args.config)
    year = args.start_year or config_mod.start_year(cfg)
    reg = registry.register(args.model_card, start_year=year)
    return _print_registration(reg)


def cmd_verify(args: argparse.Namespace) -> int:
    # Phase 1：检查真值覆盖、预测文件完整性
    print(f"verify {args.model_id}: 尚未实现（Phase 1）。")
    return 2


def cmd_reforecast(args: argparse.Namespace) -> int:
    # Phase 1：编排历史初始场回跑（Slurm）
    print(f"reforecast {args.model_id} --years {args.years}: 尚未实现（Phase 1）。")
    return 2


def cmd_score(args: argparse.Namespace) -> int:
    # Phase 1：ingest → regrid → metrics → 落盘
    print(f"score {args.model_id}: 尚未实现（Phase 1）。")
    return 2


def cmd_report(args: argparse.Namespace) -> int:
    # Phase 2：重建 leaderboard + 生成报告
    print("report: 尚未实现（Phase 2）。")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description="WeatherBench — 气象大模型测评平台",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_reg = sub.add_parser("register", help="注册模型卡（schema + 合规校验）")
    p_reg.add_argument("model_card", type=Path, help="模型卡 YAML 路径")
    p_reg.add_argument("--config", type=Path, default=None, help="benchmark.yaml 路径")
    p_reg.add_argument("--start-year", type=int, default=None, help="测评起始年（默认取配置）")
    p_reg.set_defaults(func=cmd_register)

    p_ver = sub.add_parser("verify", help="校验真值覆盖与预测完整性")
    p_ver.add_argument("model_id")
    p_ver.set_defaults(func=cmd_verify)

    p_ref = sub.add_parser("reforecast", help="编排历史初始场回跑")
    p_ref.add_argument("model_id")
    p_ref.add_argument("--years", default="2023-2025")
    p_ref.set_defaults(func=cmd_reforecast)

    p_score = sub.add_parser("score", help="打分")
    p_score.add_argument("model_id")
    p_score.set_defaults(func=cmd_score)

    p_rep = sub.add_parser("report", help="重建 leaderboard + 报告")
    p_rep.set_defaults(func=cmd_report)

    return parser


def _reconfigure_stdout() -> None:
    """Windows 控制台默认 GBK，输出统一为 UTF-8，避免编码报错。"""
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
