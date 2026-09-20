<p align="center">
  <img src="assets/logo.svg" width="132" alt="WeatherBench logo" />
</p>

<h1 align="center">WeatherBench</h1>
<p align="center"><b>气象大模型测评平台</b> · 规范化 · 可复用 · 可存档</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  <img src="https://img.shields.io/badge/status-Phase%200%20·%20WIP-orange" alt="status">
  <img src="https://img.shields.io/badge/region-China-1e3a8a" alt="region">
</p>

---

## 定位

> **模型上线前的关卡 + 上线后的对比基准。** 不是学术发榜。

为团队内部的算法/模型迭代提供一套规范化、可复用、可存档的测评系统：任何新模型进来，先**声明没看过测评年份**，再**注册 → 测评 → 存档**，团队据此判断哪个算法/模型更强、强在哪些变量/时段/区域。

*A standardized, reusable, auditable benchmark for internal weather ML model iteration — a pre-release gate plus a post-release baseline, not an academic leaderboard.*

---

## 特性

| 原则 | 含义 |
|---|---|
| **单一真值** | 所有模型打在同一套 ground truth 上，指标口径统一 |
| **注册即合规** | 模型卡是"入场券"：缺关键字段或违反 unseen-year 声明则拒绝测评 |
| **不可变存档** | 每次结果按 `model_id + 版本 + 测评配置` 原子落盘，不覆盖历史 |
| **可复用** | 新增一个模型 = 一张模型卡 + 一条命令，不改测评代码 |
| **对齐现有基建** | 复用 `foehn_core.prediction_store` 统一格式与 `UNIFIED_MAP` 变量名 |

---

## 架构与流程

```mermaid
flowchart LR
    A[注册<br/>register] --> B[合规校验<br/>unseen-year]
    B --> C[回跑<br/>reforecast]
    C --> D[标准化 · 重网格<br/>ingest + regrid]
    D --> E[打分<br/>score]
    E --> F[存档<br/>scores/]
    F --> G[出榜<br/>leaderboard]

    style A fill:#1e3a8a,color:#fff,stroke:none
    style B fill:#2563eb,color:#fff,stroke:none
    style C fill:#0ea5e9,color:#fff,stroke:none
    style D fill:#0ea5e9,color:#fff,stroke:none
    style E fill:#10b981,color:#fff,stroke:none
    style F fill:#64748b,color:#fff,stroke:none
    style G fill:#f59e0b,color:#fff,stroke:none
```

| 阶段 | 命令 | 说明 |
|---|---|---|
| 注册 | `benchmark register models/xxx.yaml` | 校验 schema + unseen-year 合规 |
| 校验 | `benchmark verify <model_id>` | 检查真值覆盖、预测文件完整性 |
| 回跑 | `benchmark reforecast <model_id> --years 2023-2025` | 编排历史初始场推理（Slurm） |
| 打分 | `benchmark score <model_id>` | ingest → regrid → metrics → 落盘 |
| 出榜 | `benchmark report` | 重建 leaderboard + 生成报告 |

**关键约束**：打分是**纯函数** `(预测, 真值, 气候态, 配置) → 指标`，可重放；回跑产物写进现有 `results/<model>/<variant>/<init>Z/predictions/`，不改变现有实时管线。

---

## 已定测评范围

| 项 | 决定 |
|---|---|
| 真值（ground truth） | **ERA5 为主**（正式 benchmark）+ IFS HRES `fc0` 近实时校验 |
| 测评年份 | **2023–2025**（对现有预训练模型均为 unseen） |
| 区域 | 中国框 `15–55°N, 70–140°E` |
| 空间分辨率 | `0.25°`（通用对比）+ `0.1°`（原生 + 保守重映射到 0.25°） |
| 时间分辨率 | `6h`（主测评，0–240h）+ `1h`（降尺度专项，0–72h） |
| 初始化时次 | `00 / 12 UTC` |
| 主指标 | 纬度加权 **RMSE** / **ACC**（气候态 1991–2020） |
| 基线 | 气候态 · 持续性(24h) · **IFS HRES** |

> 详见 [`docs/benchmark_plan.md`](docs/benchmark_plan.md)。

---

## 目录结构

```
weather-benchmark/
├── assets/logo.svg                  # Logo
├── config/
│   └── benchmark.yaml               # 测评范围（年份/区域/分辨率/时长/变量/指标）
├── registry/
│   ├── schema/model_card.schema.json  # 模型卡 JSON Schema
│   └── models/                        # 模型卡（一张卡 = 一个模型）
│       ├── graphcast-operational.yaml
│       └── aurora-0.25.yaml
├── src/benchmark/                   # 核心包
│   ├── cli.py                       # 命令行入口
│   ├── config.py                    # 配置加载 / 哈希 / 路径解析
│   ├── registry.py                  # 模型卡 schema + unseen-year 合规校验
│   ├── ingest.py                    # 数据摄取（对接 prediction_store）
│   ├── regrid.py                    # 保守重映射到 0.25°
│   ├── climatology.py               # 30 年气候态
│   ├── metrics.py                   # 纬度加权 RMSE/ACC/MAE/bias
│   ├── score.py                     # 打分纯函数
│   └── report.py                    # leaderboard / 报告
├── scripts/build_climatology.py     # 气候态构建脚本
└── docs/benchmark_plan.md           # 完整方案文档
```

---

## 快速开始

```bash
# 1. 安装（可编辑模式）
pip install -e .

# 2. 注册一张模型卡（校验 schema + unseen-year 合规）
benchmark register registry/models/aurora-0.25.yaml

# 3. 回跑 → 打分 → 出榜（Phase 1/2 逐步开放）
benchmark reforecast aurora-0.25 --years 2023
benchmark score aurora-0.25
benchmark report
```

---

## 模型卡（入场券）

模型卡是进入 benchmark 的唯一入口，字段分 **必填 / 强烈建议 / 可选** 三档：

```yaml
model_id: aurora-0.25               # 全局唯一
name: Aurora
family: aurora
version: 1.0.0
status: registered                  # registered → evaluating → archived

architecture:
  type: "3D Swin Transformer (perceiver-based foundation model)"
  parameters: 1.3e9
  resolution_deg: 0.25
  time_step_h: 6
  horizon_h: 240
  variables: [2m_temperature, 10m_u_component_of_wind, ...]

training:
  origin: pretrained-as-is          # from-scratch | finetuned | pretrained-as-is
  base_checkpoint: microsoft/aurora-0.25-pretrained
  base_checkpoint_hash: "sha256:..."  # 溯源（进正式存档的硬要求）
  training_data:
    years: [1979, 2021]
    source: "ERA5 + HRES + GFS + CMIP6 + MERRA2 (多源)"

data:
  init_source: "IFS HRES fc0 (open data)"

attestation:                        # 合规声明（硬性）
  declaration: "未使用 2023–2025 任何数据训练/微调"
  training_end_year: 2021           # 必须 < 2023，否则拒绝注册
  finetune_end_year: 2021
  signed_by: "xxx"
  date: 2026-09-20

owner: "算法团队"
```

**合规校验（register 时自动执行）**：
- `attestation.training_end_year` / `finetune_end_year` 必须 `< 测评起始年`，否则拒绝注册；
- 缺 `base_checkpoint_hash` / `code_ref` → 标记为"不可复现"，仅允许内部临时测评、不进正式存档。

---

## 指标体系与基线

**确定性指标**（所有模型通用，纬度加权）：

| 指标 | 说明 |
|---|---|
| **RMSE** | 主指标，按变量 × 气压层 × lead time |
| **ACC** | 距平相关系数（对 30 年气候态）；< 0.6 视为无天气学价值（ECMWF 惯例） |
| MAE / Bias | 辅助，查系统性偏差 |
| 风矢量 RMSE | `√(RMSE_u² + RMSE_v²)` |
| 技巧分 | `1 − RMSE_model / RMSE_baseline` |

**基线**（必须一起跑，否则分数无意义）：气候态（下限）· 持续性 24h · **IFS HRES**（黄金标准）。

---

## 路线图

| 阶段 | 交付 | 状态 |
|---|---|---|
| **Phase 0** | 目录骨架 + `benchmark.yaml` + 模型卡 schema + 两张模型卡 + 气候态脚本 | ✅ 进行中 |
| **Phase 1** | ingest + regrid + RMSE/ACC/MAE/Bias + 用 2023 单年打通 GraphCast/Aurora | ⏳ |
| **Phase 2** | 全量 2023–2025 + 基线 + leaderboard + 报告 | ⏳ |
| **Phase 3** | 降水、0.1°、1h 降尺度专项、子区域/季节细分 | ⏳ |

---

## 许可

[MIT](LICENSE) © 2026 Hexian Wang

## 参考

- WeatherBench 2 论文：<https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2023MS004019>
- WeatherBench 2 评测文档：<https://weatherbench2.readthedocs.io/en/latest/evaluation.html>
- WeatherBench FAQ：<https://sites.research.google/gr/weatherbench/faq/>
