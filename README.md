<p align="center">
  <img src="assets/logo.svg" width="132" alt="WeatherBench-MingYang-Tech logo" />
</p>

<h1 align="center">WeatherBench-MingYang-Tech</h1>
<p align="center"><b>Weather ML Model Benchmark Platform</b> · Standardized · Reusable · Auditable</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license">
  <img src="https://img.shields.io/badge/status-Phase%200%20·%20WIP-orange" alt="status">
  <img src="https://img.shields.io/badge/region-China-1e3a8a" alt="region">
</p>

---

## Positioning

> **A pre-release gate plus a post-release baseline — not an academic leaderboard.**

A standardized, reusable, auditable benchmark for internal weather ML model iteration. Any new model must first **declare it has not seen the evaluation years**, then go through **register → evaluate → archive**, so the team can tell which algorithm/model is stronger, and on which variables / lead times / regions.

---

## Principles

| Principle | Meaning |
|---|---|
| **Single ground truth** | Every model is scored against the same reference, with one metric convention |
| **Register = compliant** | The model card is the entry ticket: missing fields or an unseen-year violation rejects the model |
| **Immutable archive** | Each result is written atomically under `model_id + version + config`, never overwriting history |
| **Reusable** | Adding a model = one card + one command; no changes to the scoring code |
| **Canonical format** | Defines a reforecast format aligned with WeatherBench 2 / ERA5 conventions; the reforecast step writes it, scoring reads it |

---

## Architecture & Pipeline

```mermaid
flowchart LR
    A[Register] --> B[Compliance<br/>unseen-year]
    B --> C[Reforecast]
    C --> D[Normalize + Regrid<br/>ingest + regrid]
    D --> E[Score]
    E --> F[Archive<br/>scores/]
    F --> G[Leaderboard]

    style A fill:#1e3a8a,color:#fff,stroke:none
    style B fill:#2563eb,color:#fff,stroke:none
    style C fill:#0ea5e9,color:#fff,stroke:none
    style D fill:#0ea5e9,color:#fff,stroke:none
    style E fill:#10b981,color:#fff,stroke:none
    style F fill:#64748b,color:#fff,stroke:none
    style G fill:#f59e0b,color:#fff,stroke:none
```

| Stage | Command | Purpose |
|---|---|---|
| Register | `benchmark register models/xxx.yaml` | schema + unseen-year compliance |
| Verify | `benchmark verify <model_id>` | truth coverage & prediction completeness |
| Reforecast | `benchmark reforecast <model_id> --years 2023-2025` | orchestrate historical inference (Slurm) |
| Score | `benchmark score <model_id>` | ingest → regrid → metrics → write |
| Report | `benchmark report` | rebuild leaderboard + generate report |

**Key constraint**: scoring is a **pure function** `(predictions, truth, climatology, config) → metrics`, hence replayable; reforecast outputs go into `results/<model_id>/predictions/` in the canonical format, without touching the live pipeline.

---

## Evaluation Scope

| Item | Decision |
|---|---|
| Ground truth | **ERA5** (formal benchmark) + IFS HRES `fc0` for near-real-time check |
| Evaluation years | **2023–2025** (unseen for all current pretrained models) |
| Region | China box `15–55°N, 70–140°E` |
| Spatial resolution | `0.25°` (common grid) + `0.1°` (native, also conservatively regridded to 0.25°) |
| Temporal resolution | `6h` (primary, 0–240h) + `1h` (downscaling track, 0–72h) |
| Initialization times | `00 / 12 UTC` |
| Primary metrics | latitude-weighted **RMSE** / **ACC** (1991–2020 climatology) |
| Baselines | climatology · persistence (24h) · **IFS HRES** |

> See [`docs/benchmark_plan.md`](docs/benchmark_plan.md) for the full design document.

---

## Repository Layout

```
weather-benchmark/
├── assets/logo.svg                    # Logo
├── config/
│   └── benchmark.yaml                 # scope (years/region/resolution/duration/variables/metrics)
├── registry/
│   ├── schema/model_card.schema.json  # model-card JSON Schema
│   └── models/                        # one card per model
│       ├── graphcast-operational.yaml
│       └── aurora-0.25.yaml
├── src/benchmark/                     # core package
│   ├── cli.py                         # CLI entry point
│   ├── config.py                      # config load / hash / path resolution
│   ├── registry.py                    # card schema + unseen-year compliance
│   ├── ingest.py                      # data ingestion (canonical reforecast format)
│   ├── truth.py                       # truth / climatology loading
│   ├── regrid.py                      # conservative regrid to 0.25°
│   ├── climatology.py                 # 30-year climatology
│   ├── metrics.py                     # lat-weighted RMSE/ACC/MAE/bias
│   ├── score.py                       # pure scoring function
│   ├── pipeline.py                    # ingest → align → score → archive orchestration
│   ├── archive.py                     # immutable score archive
│   └── report.py                      # leaderboard / report
├── scripts/build_climatology.py       # climatology builder
└── docs/benchmark_plan.md             # full design document
```

---

## Quick Start

```bash
# 1. Install (editable)
pip install -e .

# 2. Register a model card (schema + unseen-year compliance)
benchmark register registry/models/aurora-0.25.yaml

# 3. Reforecast → score → report (Phase 1/2 rolling out)
benchmark reforecast aurora-0.25 --years 2023
benchmark score aurora-0.25
benchmark report
```

---

## Model Card (entry ticket)

The model card is the only way into the benchmark. Fields are grouped into **required / recommended / optional** tiers:

```yaml
model_id: aurora-0.25               # globally unique
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
  base_checkpoint_hash: "sha256:..."  # provenance (hard requirement for formal archive)
  training_data:
    years: [1979, 2021]
    source: "ERA5 + HRES + GFS + CMIP6 + MERRA2 (multi-source)"

data:
  init_source: "IFS HRES fc0 (open data)"

attestation:                        # compliance declaration (mandatory)
  declaration: "not trained or fine-tuned on any 2023–2025 data"
  training_end_year: 2021           # must be < 2023, else rejected
  finetune_end_year: 2021
  signed_by: "xxx"
  date: 2026-09-20

owner: "Algorithm Team"
```

**Compliance checks (run automatically on `register`)**:
- `attestation.training_end_year` / `finetune_end_year` must be `< the evaluation start year`, otherwise registration is rejected;
- missing `base_checkpoint_hash` / `code_ref` → flagged **non-reproducible**: internal trial only, excluded from the formal archive.

---

## Metrics & Baselines

**Deterministic metrics** (shared by all models, latitude-weighted):

| Metric | Description |
|---|---|
| **RMSE** | primary, per variable × pressure level × lead time |
| **ACC** | anomaly correlation coefficient (vs 30-yr climatology); < 0.6 = no synoptic skill (ECMWF convention) |
| MAE / Bias | auxiliary, for systematic error |
| Wind-vector RMSE | `√(RMSE_u² + RMSE_v²)` |
| Skill score | `1 − RMSE_model / RMSE_baseline` |

**Baselines** (always run together, otherwise scores are meaningless): climatology (lower bound) · persistence 24h · **IFS HRES** (gold standard).

---

## Roadmap

| Phase | Deliverable | Status |
|---|---|---|
| **Phase 0** | Repo skeleton + `benchmark.yaml` + model-card schema + two model cards + climatology script | ✅ in progress |
| **Phase 1** | ingest + regrid + RMSE/ACC/MAE/Bias + end-to-end GraphCast/Aurora on 2023 | ⏳ |
| **Phase 2** | full 2023–2025 + baselines + leaderboard + report | ⏳ |
| **Phase 3** | precipitation, 0.1°, 1h downscaling, sub-region/season breakdowns | ⏳ |

---

## License

[MIT](LICENSE) © 2026 Hexian Wang

## References

- WeatherBench 2 paper: <https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2023MS004019>
- WeatherBench 2 evaluation docs: <https://weatherbench2.readthedocs.io/en/latest/evaluation.html>
- WeatherBench FAQ: <https://sites.research.google/gr/weatherbench/faq/>
