# 气象大模型 Benchmark 平台方案

> 目标：为团队内部的算法/模型迭代提供一套**规范化、可复用、可存档**的测评系统。
> 定位：不是学术发榜，而是"模型上线前的关卡 + 上线后的对比基准"——任何新模型进来，先声明没看过测评年份，再注册、测评、存档，团队据此判断哪个算法/模型更强。

---

## 1. 背景与定位

- 已部署 GraphCast（0.25° / 6h）与 Aurora（0.25° / 6h），核心工作不是从零训练，而是**部署现有模型 + 时间降尺度（6h→1h）+ 空间分辨率（0.25°/0.1°）**。
- Benchmark 要回答三个问题：
  1. 新模型/新算法比现有 GraphCast / Aurora **强多少、在哪些变量/时段/区域强**？
  2. 模型是否**合规**（没拿测评年份当训练数据）？
  3. 一次测评后**可复现、可追溯、可对比**（换个人跑得出一致结论）。

### 设计原则（工业级）

1. **单一真值**：所有模型打在同一套 ground truth 上，指标口径统一。
2. **注册即合规**：模型卡是"入场券"，缺关键字段或违反 unseen-year 声明则拒绝测评。
3. **不可变存档**：每次测评的结果按 `model_id + 版本 + 测评配置` 原子落盘，不覆盖历史。
4. **可复用**：新增一个模型 = 一张模型卡 + 一条命令，不用改测评代码。
5. **与现有基建对齐**：复用 `foehn_core.prediction_store` 的统一预测格式，不另起炉灶。

---

## 2. 核心概念

| 术语 | 含义 |
|---|---|
| **model_id** | 全局唯一标识，如 `aurora-0.25-finetuned`、`graphcast-operational` |
| **模型卡 (model card)** | 注册时提交的 YAML/JSON，含架构、训练、数据、声明等（见 §7） |
| **测评配置 (benchmark config)** | 一次测评的范围：年份、区域、分辨率、时长、变量、指标 |
| **真值 (ground truth)** | 用于打分的观测/分析场（ERA5 或 IFS HRES 分析） |
| **reforecast** | 用历史初始场回跑模型，得到测评年份的预报结果 |
| **score** | 对回跑结果算指标，产出 metric cube + 摘要 |

---

## 3. 测评范围定义

### 3.1 区域

主区域沿用现有 `prediction_store` 的 China 框：

```
lat: 15.0 – 55.0°N
lon: 70.0 – 140.0°E
```

**建议**：在此基础上增加 3 个子区域做分区评分（气象上分区才有意义）：

| 子区域 | lat | lon | 意义 |
|---|---|---|---|
| 华东/沿海 | 22–40 | 105–125 | 经济核心、强对流/台风影响 |
| 华南 | 18–27 | 105–120 | 台风、降水 |
| 青藏高原 | 27–40 | 78–105 | 地形复杂、模式难点 |

> 子区域可选，MVP 先只做全国框，后续再加。

### 3.2 空间分辨率

- **通用对比网格：0.25°**（两个模型的公共分母，也是中国区精细度的合理平衡点）。
- 0.1° 模型：**原生分辨率打一次分 + 保守重网格到 0.25° 再打一次**，保证可对比性。
- 重网格用 **一阶保守重映射**（与 WeatherBench 2 一致）。

### 3.3 时间分辨率与预测时长（本方案决定）

| 模型时间步 | 预测时长 | 打分 lead time | 用途 |
|---|---|---|---|
| **6h 模型**（GraphCast/Aurora 现状） | **0–240h（10 天）** | 6,12,…,240h（40 步） | 主测评 |
| **1h 模型**（降尺度目标） | **0–72h** | 1,2,…,72h | 时间降尺度专项 |
| 跨模型对比 | — | **6h 的倍数**（6,12,…,72h） | 统一口径 |

> 主测评用 6h 步长 0–240h，与现有 pipeline 的 40 步完全一致；1h 作为降尺度专项单独评，不强制所有模型都支持。

### 3.4 变量

统一变量名（来自现有 `UNIFIED_MAP`）：

| 类别 | 变量 | 说明 |
|---|---|---|
| 地面 | `2m_temperature` | 核心 |
| 地面 | `10m_u/v_component_of_wind` | 合成风矢量/风速 |
| 地面 | `mean_sea_level_pressure` | 核心 |
| 高空 | `geopotential` @ 500hPa | 大形势核心指标 |
| 高空 | `temperature` @ 850/500/250hPa | |
| 高空 | `u/v_component_of_wind` @ 850/250hPa | 急流 |
| 高空 | `specific_humidity` @ 850hPa | |

**缺口（明确列为扩展项）**：降水、云量、辐射、能见度。当前两个模型都不输出降水，而降水对中国区业务最重要——需要在 Phase 3 单独解决（换/加模型或后处理）。

---

## 4. 测评年份与数据划分（含调研结论）

### 调研结论（行业规范）

- **WeatherBench 2（事实标准）** 用 **2020 年** 做测试年：在"足够近"与"样本稳健"之间折中，且 2018/2020 的分数差异很小。
- 主流模型训练/测试切分（截至 2026 调研）：
  - GraphCast：训练 1979–2017，验证 2018
  - GenCast：训练 1979–2018
  - AIFS：训练 1979–2020
  - Pangu-Weather：约 1979–2021（43 年）
  - Aurora：多源预训练，最新截止约 2021
  - NeuralGCM：训练 1979–2019
- 关键结论：所有主流模型训练截止 ≤ 2021，故 2023 起对任何模型都"未见过"；**2022 是灰色区**（Pangu/Aurora 可能训练到 2021），不作为测试年。
- 通用做法：**测试年必须严格晚于训练截止年**，且用 ERA5 做真值，气候态取 30 年（如 1991–2020）。

### 本方案推荐

**主测评年：2023–2025（三年）**，理由：

1. **近、符合当前气候**：对业务迭代最有参考价值。
2. **对预训练模型是"未见过"的**：GraphCast 训练到 2017、Aurora 基础模型也早于 2023，天然满足 unseen-year 要求。
3. **ERA5 已可用**：ERA5 final 有约 2–3 个月延迟，2025 年在 2026 年 9 月已完整可获取。

**已定（2026-09-18 拍板）**：只用 **2023–2025**，不保留 2020 学术对照年。

> ⚠️ 注意：23–25 三年回跑的**数据量/算力成本**不小（见 §12），建议先跑 2024 单年打通，再全量三年。

---

## 5. 真值数据（ground truth）

两个候选（已定，2026-09-18 拍板）：

| 方案 | 优点 | 缺点 | 适用 |
|---|---|---|---|
| **A. ERA5（学术标准）** | 质量最高（4D-Var 再分析）、可对标已发表分数、气象界默认 | 有 2–3 月延迟、与模型初始场（IFS HRES）口径略有出入 | 正式 benchmark、学术对标 |
| **B. IFS HRES 分析（fc0）** | 就是你现有 pipeline 的初始场来源，口径一致、近实时 | 非再分析、无已发表对标基线 | 日常业务快速评估 |

**已定**：**A 为主（ERA5）**，B 作为近实时的快速校验通道。真值统一重网格到 0.25° 基准网格后落盘缓存，避免每次打分重复下载。

---

## 6. 指标体系（含基线）

### 6.1 确定性指标（所有模型通用，纬度加权）

- **RMSE**（按变量、按气压层、按 lead time）——主指标
- **ACC（距平相关系数）**——相对 30 年气候态（1991–2020），衡量"趋势/异常"抓得对不对；**ACC < 0.6 视为无天气学价值**（ECMWF 惯例）
- **MAE**、**Bias（平均误差）**——辅助，查系统性偏差
- **风矢量 RMSE** = sqrt(RMSE_u² + RMSE_v²)——风速/风矢量分开报

纬度权重：`w(i) = (sinθᵢᵘ − sinθᵢˡ) / mean(sinθᵘ − sinθˡ)`（WeatherBench 2 定义）。

### 6.2 汇总口径

- lead-time 曲线（横轴 lead，纵轴指标）
- 分时段均值：**Day1–3 / Day4–6 / Day7–10**
- 分季节：DJF / MAM / JJA / SON
- 分区域：全国框 + 3 子区域
- **技巧分 (skill score)**：`1 − RMSE_model / RMSE_baseline`

### 6.3 基线（必须一起跑，否则分数没有意义）

1. **气候态 (climatology)**：ERA5 30 年逐日气候态 → 下限
2. **持续性 (persistence)**：24h 持续性预报 → 简单基线
3. **IFS HRES（业务模式）**：你要对标/追赶的"黄金标准"
4. （可选）**ERA5 分析本身**：作为"上界参考"

---

## 7. 模型注册规范（模型卡 schema）

这是"入场券"。字段分**必填 / 强烈建议 / 可选**三档。

```yaml
model_id: aurora-0.25-finetuned        # 全局唯一
name: Aurora
family: aurora
variant: 0.25-finetuned
version: 1.0.0
status: registered                     # registered → evaluating → archived

architecture:                          # 必填
  type: "3D Swin Transformer (perceiver-based)"
  parameters: 1.3e9
  resolution_deg: 0.25
  time_step_h: 6
  horizon_h: 240
  variables: [2m_temperature, 10m_wind, mslp, z, t, u, v, q]   # 输出变量清单

training:                              # 必填
  origin: finetuned                    # from-scratch | finetuned | pretrained-as-is
  base_checkpoint: microsoft/aurora-0.25-pretrained
  base_checkpoint_hash: sha256:...     # 溯源
  finetuning:
    enabled: true
    data_years: [2022]                 # 微调数据（必须晚于训练截止、早于测试年）
    data_source: "IFS HRES analysis"
    epochs: 3
    hardware: "8 × MI250X"
    wall_time_h: 12
  training_data:                       # 基础模型的训练数据（引用原文/元数据）
    years: [1979, 2017]
    source: ERA5

data:                                  # 必填
  init_source: "IFS HRES fc0 (open data)"
  input_variables: [...]

attestation:                           # 必填 —— 合规声明
  declaration: "模型及其基础 checkpoint 未使用 2023–2025 任何数据训练/微调"
  training_end_year: 2017              # 硬性：必须 < 2023
  finetune_end_year: 2022
  signed_by: "xxx"
  date: 2026-09-18

owner: "团队/个人"
contact: "..."

reproducibility:                       # 强烈建议
  conda_env: "infer-gpu (spec hash)"
  code_ref: "<git commit sha>"
  seed: 42
  hardware: "Setonix MI250X"
```

**合规校验（register 时自动检查）**：
- `attestation.training_end_year` 与 `attestation.finetune_end_year` 必须 **< 测评起始年（2023）**，否则拒绝注册；
- 缺 `base_checkpoint_hash` / `code_ref` 则标记为"不可复现"，只允许内部临时测评，不进正式存档。

---

## 8. 测评流程（pipeline）

```
注册 → 合规校验 → 回跑(reforecast) → 标准化/重网格 → 打分 → 存档 → 出榜
```

| 阶段 | 命令 | 说明 |
|---|---|---|
| 注册 | `benchmark register models/xxx.yaml` | 校验 schema + unseen-year 合规 |
| 校验 | `benchmark verify <model_id>` | 检查真值覆盖、预测文件完整性 |
| 回跑 | `benchmark reforecast <model_id> --years 2023-2025` | 编排历史初始场的推理（Slurm） |
| 打分 | `benchmark score <model_id>` | ingest→regrid→metrics→落盘 |
| 出榜 | `benchmark report` | 重建 leaderboard + 生成报告 |

**关键约束**：
- 回跑产物直接写进现有 `results/<model>/<variant>/<init>Z/predictions/`，**不改变现有实时 pipeline**；
- 打分是**纯函数**：`(预测, 真值, 气候态, 配置) → 指标`，可重放；
- 每次 score 生成 `metric cube`（NetCDF）+ `summary.json` + `report.md/html`，按 `score_id` 原子落盘。

---

## 9. 存档与对比（leaderboard）

### 目录结构

```
benchmark/
  config/
    benchmark.yaml                 # 测评范围（年份/区域/分辨率/时长/变量/指标）
  registry/
    models/
      aurora-0.25-finetuned.yaml
      graphcast-operational.yaml
  data/
    truth/                         # 真值（ERA5/IFS）重网格缓存
    climatology/                   # 30 年气候态
    baselines/                     # 气候态/持续性/IFS 的评分结果
  scores/
    <model_id>/<version>/
      metrics.nc                   # 指标张量 (metric × var × level × lead × region)
      summary.json                 # 人类可读摘要
      report.md / report.html
  leaderboard.json                 # 聚合排名快照
  src/benchmark/
    registry.py   ingest.py   regrid.py
    climatology.py   metrics.py   score.py   report.py
  cli.py
```

### 对比规则

- **同口径才可比**：同一年份、同区域、同重网格、同一套指标。
- leaderboard 记录 `model_id + version + score_id + 配置 hash`，任何配置变化都产生新行，**不覆盖**。
- 排名维度：主指标（RMSE / ACC）按变量、按时段、按区域分列，支持过滤查看。

---

## 10. 工具设计要点

- 语言：Python + xarray（与现有 `foehn_core` 一致）。
- 评分核心复用/对齐 WeatherBench 2 的指标定义（lat-weighted RMSE/ACC、保守重网格），但不引入其 Beam 依赖，先用 in-memory，数据量大再上并行。
- CLI 用现有项目风格（`argparse`），配置用 YAML，模型卡用 YAML + JSON Schema 校验。
- 重网格、气候态、真值都**预计算并缓存**，打分阶段只做纯计算。

---

## 11. 分阶段路线图

| 阶段 | 交付 | 周期（估） |
|---|---|---|
| **Phase 0** | 目录骨架 + `benchmark.yaml` + 模型卡 schema + 两张现有模型卡 + 气候态构建脚本 | ~1 周 |
| **Phase 1** | ingest + regrid + 核心指标（RMSE/ACC/MAE/Bias）+ 用 2024 单年打通 GraphCast/Aurora 打分 | ~1–2 周 |
| **Phase 2** | 全量 2023–2025 + 基线（气候态/持续性/IFS）+ leaderboard + 报告 | ~2–3 周 |
| **Phase 3** | 扩展：降水、0.1°、1h 降尺度专项、集合预报、子区域/季节细分 | 持续 |

---

## 12. 风险与待决事项

### 已定事项（2026-09-18 拍板）
1. **真值**：ERA5 为主 + IFS HRES 分析做近实时校验（§5）。
2. **测评年份**：2023–2025，不保留 2020 学术对照年（§4）。
3. **回跑成本**（待评估预算）：三年 × 每日 2 时次 × 40 步 × 中国框（每场约 0.4GB），建议先 2024 单年打通再全量。

### 风险
- **回跑数据量/算力**：三年全量回跑是最大成本项，建议先 2024 单年验证再扩。
- **降水缺失**：两个模型都不输出降水，中国区业务关键变量，需 Phase 3 单独处理。
- **初始场口径**：模型用 IFS HRES 初始场、却拿 ERA5 打分，存在小幅系统性偏差，需在报告中声明（这也是 WeatherBench 2 的处理方式）。
- **unseen-year 声明依赖自报**：靠 `training_end_year` + checkpoint 溯源 + 哈希来审计，无法绝对防伪。
- **ERA5 许可**：CC-BY-4.0，内部使用无碍；若要对外公开 benchmark 数据需注明出处。

---

## 参考

- WeatherBench 2 论文：<https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2023MS004019>
- WeatherBench 2 评测文档：<https://weatherbench2.readthedocs.io/en/latest/evaluation.html>
- WeatherBench FAQ（数据/年份/指标）：<https://sites.research.google/gr/weatherbench/faq/>
