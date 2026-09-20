# Weather ML Model Benchmark Platform — Design Plan

> Goal: a **standardized, reusable, auditable** evaluation system for internal algorithm/model iteration.
> Positioning: not an academic leaderboard, but a "pre-release gate + post-release baseline" — any new model first declares it has not seen the evaluation years, then registers, evaluates, and archives, so the team can judge which algorithm/model is stronger.

---

## 1. Background & Positioning

- GraphCast (0.25° / 6h) and Aurora (0.25° / 6h) are already deployed; the core work is not training from scratch but **deploying existing models + temporal downscaling (6h→1h) + spatial resolution (0.25°/0.1°)**.
- The benchmark must answer three questions:
  1. How much better is a new model/algorithm than the current GraphCast / Aurora, and **on which variables / lead times / regions**?
  2. Is the model **compliant** (did it not use the evaluation years as training data)?
  3. Is one evaluation **reproducible, traceable, and comparable** (does another person get the same conclusion)?

### Design principles (industrial grade)

1. **Single ground truth**: every model is scored against the same reference with one metric convention.
2. **Register = compliant**: the model card is the entry ticket; missing fields or an unseen-year violation rejects the model.
3. **Immutable archive**: each result is written atomically under `model_id + version + config`, never overwriting history.
4. **Reusable**: adding a model = one card + one command, no changes to the scoring code.
5. **Canonical format**: the benchmark defines a reforecast format aligned with WeatherBench 2 / ERA5 conventions (same variable names, `latitude`/`longitude` coords); the reforecast step writes it, scoring reads it. (Earlier drafts assumed a `foehn_core.prediction_store` unified format — that does not exist on Pawsey, so the benchmark owns the format.)

---

## 2. Core Concepts

| Term | Meaning |
|---|---|
| **model_id** | globally unique identifier, e.g. `aurora-0.25-finetuned`, `graphcast-operational` |
| **model card** | YAML/JSON submitted at registration: architecture, training, data, declaration (see §7) |
| **benchmark config** | the scope of one evaluation: years, region, resolution, duration, variables, metrics |
| **ground truth** | the observation/analysis used for scoring (ERA5 or IFS HRES analysis) |
| **reforecast** | re-running a model on historical initial conditions to produce forecasts for the evaluation years |
| **score** | computing metrics on reforecast outputs, producing a metric cube + summary |

---

## 3. Evaluation Scope

### 3.1 Region

The primary region is the China box:

```
lat: 15.0 – 55.0°N
lon: 70.0 – 140.0°E
```

**Recommendation**: add 3 sub-regions for regional scoring (meteorologically meaningful splits):

| Sub-region | lat | lon | Rationale |
|---|---|---|---|
| East China / coastal | 22–40 | 105–125 | economic core, convection/typhoon impact |
| South China | 18–27 | 105–120 | typhoons, precipitation |
| Tibetan Plateau | 27–40 | 78–105 | complex terrain, model pain point |

> Sub-regions are optional; the MVP uses the full China box first, adding them later.

### 3.2 Spatial Resolution

- **Common comparison grid: 0.25°** (the common denominator of both models and a reasonable balance for China-wide detail).
- 0.1° models: **scored once at native resolution + once after conservative regridding to 0.25°**, to keep comparability.
- Regridding uses **first-order conservative remapping** (consistent with WeatherBench 2).

### 3.3 Temporal Resolution & Forecast Length (decided in this plan)

| Model time step | Forecast length | Scoring lead times | Purpose |
|---|---|---|---|
| **6h models** (GraphCast/Aurora today) | **0–240h (10 days)** | 6,12,…,240h (40 steps) | primary |
| **1h models** (downscaling target) | **0–72h** | 1,2,…,72h | temporal downscaling track |
| Cross-model comparison | — | **multiples of 6h** (6,12,…,72h) | unified convention |

> The primary track uses 6h steps over 0–240h, identical to the existing pipeline's 40 steps; 1h is a separate downscaling track, not mandatory for all models.

### 3.4 Variables

Unified variable names (WeatherBench 2 / ERA5 long names, matching the Aurora ``Batch`` output):

| Category | Variable | Note |
|---|---|---|
| Surface | `2m_temperature` | core |
| Surface | `10m_u/v_component_of_wind` | combined wind vector / speed |
| Surface | `mean_sea_level_pressure` | core |
| Upper-air | `geopotential` @ 500hPa | key large-scale pattern metric |
| Upper-air | `temperature` @ 850/500/250hPa | |
| Upper-air | `u/v_component_of_wind` @ 850/250hPa | jet stream |
| Upper-air | `specific_humidity` @ 850hPa | |

**Gaps (explicitly deferred as extensions)**: precipitation, cloud cover, radiation, visibility. Neither current model outputs precipitation, which is the most operationally important variable for the China region — to be solved in Phase 3 (swap/add a model or post-process).

---

## 4. Evaluation Years & Data Split (with research findings)

### Research findings (industry convention)

- **WeatherBench 2 (de-facto standard)** uses **2020** as the test year: a balance between "recent enough" and "sample robustness"; 2018/2020 score differences are small.
- Mainstream model train/test splits (as of 2026 research):
  - GraphCast: train 1979–2017, validate 2018
  - GenCast: train 1979–2018
  - AIFS: train 1979–2020
  - Pangu-Weather: ~1979–2021 (43 years)
  - Aurora: multi-source pretraining, latest cutoff ~2021
  - NeuralGCM: train 1979–2019
- Key conclusion: all mainstream models have training cutoffs ≤ 2021, so 2023 onward is "unseen" for any of them; **2022 is a gray zone** (Pangu/Aurora may have trained through 2021), so it is not used as a test year.
- Common practice: **the test year must be strictly later than the training cutoff**, ERA5 is used as truth, and climatology spans 30 years (e.g. 1991–2020).

### Recommendation in this plan

**Primary evaluation years: 2023–2025 (three years)**, because:

1. **Recent, matches the current climate**: most useful for operational iteration.
2. **"Unseen" for pretrained models**: GraphCast trains through 2017, Aurora's base model also predates 2023, naturally satisfying unseen-year.
3. **ERA5 is available**: ERA5 final has ~2–3 months latency; 2025 is fully retrievable by September 2026.

**Locked (2026-09-18)**: use **2023–2025 only**, drop the 2020 academic anchor year.

> ⚠️ Note: a three-year reforecast is a significant data/compute cost (see §12); run 2024 alone first to prove the pipeline, then the full three years.

---

## 5. Ground Truth

Two candidates (locked, 2026-09-18):

| Option | Pros | Cons | Use |
|---|---|---|---|
| **A. ERA5 (academic standard)** | highest quality (4D-Var reanalysis), comparable to published scores, meteorology default | ~2–3 months latency; slightly different convention vs model initial conditions (IFS HRES) | formal benchmark, academic comparison |
| **B. IFS HRES analysis (fc0)** | exactly your pipeline's initial-condition source, consistent convention, near-real-time | not a reanalysis, no published baseline | daily operational quick check |

**Locked**: **A primary (ERA5)**, B as the near-real-time quick-check channel. Truth is uniformly regridded to the 0.25° reference grid and cached, avoiding repeated downloads per score.

---

## 6. Metrics (with baselines)

### 6.1 Deterministic metrics (shared by all models, latitude-weighted)

- **RMSE** (per variable, per pressure level, per lead time) — primary
- **ACC (anomaly correlation coefficient)** — vs the 30-yr climatology (1991–2020), measures whether "trend/anomaly" is captured; **ACC < 0.6 = no synoptic skill** (ECMWF convention)
- **MAE**, **Bias (mean error)** — auxiliary, for systematic error
- **Wind-vector RMSE** = sqrt(RMSE_u² + RMSE_v²) — wind speed / vector reported separately

Latitude weight: `w(lat) = cos(lat) / mean(cos(lat))` (WeatherBench 2 convention).

### 6.2 Aggregation conventions

- lead-time curves (x = lead time, y = metric)
- period means: **Day1–3 / Day4–6 / Day7–10**
- by season: DJF / MAM / JJA / SON
- by region: full China box + 3 sub-regions
- **skill score**: `1 − RMSE_model / RMSE_baseline`

### 6.3 Baselines (always run together, otherwise scores are meaningless)

1. **Climatology**: ERA5 30-yr daily climatology → lower bound
2. **Persistence**: 24h persistence forecast → simple baseline
3. **IFS HRES (operational model)**: the "gold standard" to benchmark/beat
4. (optional) **ERA5 analysis itself**: an "upper-bound reference"

---

## 7. Model Registration (model card schema)

This is the entry ticket. Fields are grouped into **required / recommended / optional** tiers.

```yaml
model_id: aurora-0.25-finetuned        # globally unique
name: Aurora
family: aurora
variant: 0.25-finetuned
version: 1.0.0
status: registered                     # registered → evaluating → archived

architecture:                          # required
  type: "3D Swin Transformer (perceiver-based)"
  parameters: 1.3e9
  resolution_deg: 0.25
  time_step_h: 6
  horizon_h: 240
  variables: [2m_temperature, 10m_wind, mslp, z, t, u, v, q]   # output variable list

training:                              # required
  origin: finetuned                    # from-scratch | finetuned | pretrained-as-is
  base_checkpoint: microsoft/aurora-0.25-pretrained
  base_checkpoint_hash: sha256:...     # provenance
  finetuning:
    enabled: true
    data_years: [2022]                 # fine-tune data (later than train cutoff, earlier than test year)
    data_source: "IFS HRES analysis"
    epochs: 3
    hardware: "8 × MI250X"
    wall_time_h: 12
  training_data:                       # base model's training data (cite original paper/metadata)
    years: [1979, 2017]
    source: ERA5

data:                                  # required
  init_source: "IFS HRES fc0 (open data)"
  input_variables: [...]

attestation:                           # required — compliance declaration
  declaration: "the model and its base checkpoint were not trained/fine-tuned on any 2023–2025 data"
  training_end_year: 2017              # hard: must be < 2023
  finetune_end_year: 2022
  signed_by: "xxx"
  date: 2026-09-18

owner: "team/person"
contact: "..."

reproducibility:                       # recommended
  conda_env: "infer-gpu (spec hash)"
  code_ref: "<git commit sha>"
  seed: 42
  hardware: "Setonix MI250X"
```

**Compliance checks (run automatically on `register`)**:
- `attestation.training_end_year` and `attestation.finetune_end_year` must be **< the evaluation start year (2023)**, otherwise registration is rejected;
- missing `base_checkpoint_hash` / `code_ref` → flagged **non-reproducible**: internal trial only, excluded from the formal archive.

---

## 8. Pipeline

```
register → compliance check → reforecast → normalize/regrid → score → archive → leaderboard
```

| Stage | Command | Purpose |
|---|---|---|
| Register | `benchmark register models/xxx.yaml` | schema + unseen-year compliance |
| Verify | `benchmark verify <model_id>` | truth coverage & prediction completeness |
| Reforecast | `benchmark reforecast <model_id> --years 2023-2025` | orchestrate historical inference (Slurm) |
| Score | `benchmark score <model_id>` | ingest → regrid → metrics → write |
| Report | `benchmark report` | rebuild leaderboard + generate report |

**Key constraints**:
- reforecast outputs go directly into the existing `results/<model>/<variant>/<init>Z/predictions/`, **without touching the live pipeline**;
- scoring is a **pure function**: `(predictions, truth, climatology, config) → metrics`, replayable;
- each score produces a `metric cube` (NetCDF) + `summary.json` + `report.md/html`, written atomically under a `score_id`.

---

## 9. Archive & Comparison (leaderboard)

### Directory structure

```
benchmark/
  config/
    benchmark.yaml                 # scope (years/region/resolution/duration/variables/metrics)
  registry/
    models/
      aurora-0.25-finetuned.yaml
      graphcast-operational.yaml
  data/
    truth/                         # truth (ERA5/IFS) regrid cache
    climatology/                   # 30-yr climatology
    baselines/                     # scores for climatology/persistence/IFS
  scores/
    <model_id>/<version>/
      metrics.nc                   # metric tensor (metric × var × level × lead × region)
      summary.json                 # human-readable summary
      report.md / report.html
  leaderboard.json                 # aggregated ranking snapshot
  src/benchmark/
    registry.py   ingest.py   regrid.py
    climatology.py   metrics.py   score.py   report.py
  cli.py
```

### Comparison rules

- **Comparable only under the same convention**: same year, region, regrid, and metric set.
- The leaderboard records `model_id + version + score_id + config hash`; any config change creates a new row, **never overwriting**.
- Ranking dimensions: primary metrics (RMSE / ACC) split by variable, period, and region, with filtering.

---

## 10. Tooling Design

- Language: Python + xarray (consistent with the existing `foehn_core`).
- Scoring core reuses/aligns with WeatherBench 2 metric definitions (lat-weighted RMSE/ACC, conservative regrid), but without its Beam dependency — in-memory first, parallelize only when data volume demands it.
- CLI in the existing project style (`argparse`), config in YAML, model cards in YAML validated against a JSON Schema.
- Regrid, climatology, and truth are **precomputed and cached**; the scoring stage does pure computation only.

---

## 11. Roadmap

| Phase | Deliverable | Estimate |
|---|---|---|
| **Phase 0** | repo skeleton + `benchmark.yaml` + model-card schema + two existing model cards + climatology script | ~1 week |
| **Phase 1** | ingest + regrid + core metrics (RMSE/ACC/MAE/Bias) + end-to-end GraphCast/Aurora on 2024 | ~1–2 weeks |
| **Phase 2** | full 2023–2025 + baselines (climatology/persistence/IFS) + leaderboard + report | ~2–3 weeks |
| **Phase 3** | extensions: precipitation, 0.1°, 1h downscaling, ensembles, sub-region/season breakdowns | ongoing |

---

## 12. Risks & Open Items

### Locked items (2026-09-18)
1. **Truth**: ERA5 primary + IFS HRES analysis for near-real-time check (§5).
2. **Evaluation years**: 2023–2025, drop the 2020 academic anchor (§4).
3. **Reforecast cost** (budget TBD): 3 years × 2 init times/day × 40 steps × China box (~0.4GB per run) — run 2024 alone first, then scale.

### Risks
- **Reforecast data/compute**: the full three-year reforecast is the largest cost; validate on 2024 first.
- **Missing precipitation**: neither model outputs precipitation, an operationally critical variable for China — solve in Phase 3.
- **Initial-condition convention**: models use IFS HRES initial conditions but are scored against ERA5, introducing a small systematic bias — declare in the report (this is also how WeatherBench 2 handles it).
- **Unseen-year declaration relies on self-reporting**: audited via `training_end_year` + checkpoint provenance + hash, not absolutely tamper-proof.
- **ERA5 license**: CC-BY-4.0, fine for internal use; attribute if benchmark data is published externally.

---

## References

- WeatherBench 2 paper: <https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2023MS004019>
- WeatherBench 2 evaluation docs: <https://weatherbench2.readthedocs.io/en/latest/evaluation.html>
- WeatherBench FAQ (data/years/metrics): <https://sites.research.google/gr/weatherbench/faq/>
