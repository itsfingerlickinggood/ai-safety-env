# HUD AI-Safety Paper Reproduction

<p align="center">
  <strong>A tamper-resistant RL environment for testing whether an AI agent can forecast, reproduce, ablate, and critique AI-safety research.</strong>
</p>

<p align="center">
  <img alt="Python 3.12" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="HUD 0.6.15" src="https://img.shields.io/badge/HUD-0.6.15-111827">
  <img alt="Status: package incomplete" src="https://img.shields.io/badge/status-package%20incomplete-F59E0B">
  <img alt="Network disabled" src="https://img.shields.io/badge/agent%20network-disabled-DC2626">
</p>

> [!IMPORTANT]
> **Core v1 is a bounded independent reproduction, not a replay of the paper's original model calls.** The public repository intentionally excludes real score traces, answer keys, frozen references, hidden variants, provider responses, and credentials. Do not deploy until the private study package passes strict preflight.

---

## The idea in one picture

```mermaid
flowchart LR
    P["Results-redacted<br/>AI-safety paper"] --> R["Research agent"]
    R --> F["Forecast"]
    R --> E["Experiment plan"]
    F --> L{"Valid and<br/>hash-locked?"}
    E --> L
    L -- No --> W["No study data<br/>No reward"]
    L -- Yes --> D["Release offline<br/>study package"]
    D --> A["Run 9 analyses<br/>+ 3 ablations"]
    A --> S["Executable submission<br/>+ scientific report"]
    S --> G["Private grader"]
    G --> N["Numerical fidelity"]
    G --> H["Hidden robustness"]
    G --> I["Scientific interpretation"]
```

The benchmark asks a stricter question than “can the model summarize a paper?”

> **Can an autonomous research agent commit to predictions, execute a real analysis, survive hidden variations, and report non-replication honestly?**

---

## What is evaluated?

| Capability | Observable behavior | Why it matters |
|---|---|---|
| 🔮 **Forecasting** | Predicts registered outcomes with uncertainty before seeing data | Measures research intuition without hindsight |
| 🧭 **Experimental design** | Maps every analysis to data, parameters, controls, and falsification criteria | Distinguishes executable plans from plausible prose |
| 🧮 **Reproduction** | Produces schema-valid numerical results for every cell | Tests end-to-end scientific execution |
| 🧪 **Ablation** | Runs fixed-budget, ordering, and conservatism checks | Tests methodological sensitivity |
| 🕵️ **Robustness** | Re-runs its code on a deterministic private variant | Penalizes hardcoding and answer reconstruction |
| 📝 **Interpretation** | Separates supported, insufficient, and unsupported claims | Rewards scientific honesty instead of forced success |

| ✅ This repository is | ❌ This repository is not |
|---|---|
| A long-horizon research-agent environment | A paper-summary benchmark |
| A bounded reproduction on newly collected traces | An exact historical replay |
| A forecast-then-experiment protocol | A task where the answer is visible in context |
| A mixed deterministic + report-judge evaluation | A purely subjective LLM-as-judge task |
| A framework for measuring research integrity | Proof that agents can already do trustworthy science |

---

## Two deliberately separate tasksets

```mermaid
flowchart TB
    REPO["This repository"]
    REPO --> CORE["Core v1<br/>official research target"]
    REPO --> REG["Monitoring regression<br/>synthetic engineering check"]
    CORE --> C1["Forecast"]
    CORE --> C2["Reproduce"]
    CORE --> C3["Ablate"]
    CORE --> C4["Interpret"]
    REG --> R1["Deterministic fixture"]
    REG --> R2["Fast lifecycle regression"]
```

| Taskset | Entrypoints | Purpose | Core v1 score? |
|---|---|---|:---:|
| **AI Safety Paper Reproduction – Core v1** | `env.py`, `tasks_paper.py` | Official forecast → reproduce → critique task | **Yes** |
| **AI Safety Monitoring Regression** | `env_monitoring.py`, `tasks_monitoring.py` | Retained deterministic regression test | No |

The regression task can detect broken environment plumbing. It cannot establish that Core v1 is scientifically valid or deployment-ready.

---

## The Core v1 study

Core v1 reproduces the central 3×3 study from *Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations* using a newly collected, provenance-bound current-model dataset.

### Registered study matrix

| Score type ↓ / challenge stratum → | Low | Mid | High |
|---|:---:|:---:|:---:|
| **Binary** | `low_binary` | `mid_binary` | `high_binary` |
| **Ordinal** | `low_ordinal` | `mid_ordinal` | `high_ordinal` |
| **Continuous** | `low_continuous` | `mid_continuous` | `high_continuous` |

```text
20 fixed items × 4 epochs = 80 scored observations per cell
9 cells × 80 observations = 720 model calls in the complete study
```

| Required ablation | Question |
|---|---|
| `fixed_budget_baseline` | Does adaptive stopping improve on a fixed evaluation budget? |
| `item_order_sensitivity` | Is the result stable when item order changes? |
| `stopping_conservatism_sensitivity` | How sensitive is the result to stopping-rule conservatism? |

> [!NOTE]
> `low`, `mid`, and `high` are preregistered challenge strata, not claims about observed performance. The final report must test whether the collected data support that ordering.

---

## The agent's journey

```mermaid
sequenceDiagram
    autonumber
    participant H as HUD
    participant W as Trusted watcher
    participant A as Research agent
    participant P as Private grader
    H->>A: Seed redacted paper, schemas, and protocol
    A->>A: Read methods and formulate hypotheses
    A->>W: Write forecast.json
    A->>W: Write experiment_plan.json
    W->>W: Validate, hash, and lock both artifacts
    alt Invalid or incomplete
        W-->>A: Keep phase two hidden
    else Valid and locked
        W->>A: Atomically release phase_two/
        W->>A: Write PHASE_TWO_READY
    end
    A->>A: Run 9 analyses and 3 ablations
    A->>A: Build reusable submission.py
    A->>H: Submit results, code, and report
    H->>P: Copy regular files into isolated grading tree
    P->>P: Compare against frozen reference
    P->>P: Run submission.py on one hidden variant
    P-->>H: Component scores + report evidence
```

### Phase 1 — preregister before outcomes

The agent sees the results-redacted paper, provenance record, protocol, and forecast/plan schemas. It must write:

```text
forecast.json
experiment_plan.json
```

The trusted watcher validates and hashes both files. Experimental traces stay hidden until both artifacts are structurally valid.

### Phase 2 — reproduce, stress-test, and report

After `PHASE_TWO_READY`, the agent receives validated offline score traces, pinned analysis code, a complete analysis manifest, and strict result schemas. It must produce:

```text
reproduction_results.json
ablations.json
final_report.md
submission.py
```

The grader runs `submission.py` again on an unseen score matrix. Memorized public values cannot pass that check.

---

## Information boundaries

```mermaid
flowchart LR
    subgraph PUBLIC["Public repository"]
        PR["Redacted paper"]
        SC["Schemas"]
        PC["Pinned analysis code"]
        CP["Collection protocol"]
    end
    subgraph OUTSIDE["Secure collection machine"]
        KEY["HUD_API_KEY"]
        RAW["Raw responses"]
        AK["Answer keys"]
        SCORE["Normalized traces"]
    end
    subgraph IMAGE["Evaluator image"]
        AGENT["Unprivileged offline<br/>agent workspace"]
        PRIVATE["Root-only verifier<br/>and references"]
    end
    CP --> OUTSIDE
    SCORE -->|validated package| AGENT
    SCORE -->|reference freeze| PRIVATE
    PR --> AGENT
    SC --> AGENT
    PC --> AGENT
    KEY -. never copied .-> AGENT
    RAW -. never copied .-> AGENT
    AK -. never copied .-> AGENT
    PRIVATE -. unreadable .-> AGENT
```

| Artifact | GitHub | Agent | Private grader | Collection machine |
|---|:---:|:---:|:---:|:---:|
| Redacted paper and methods | ✅ | ✅ | ✅ | Optional |
| Output schemas | ✅ | ✅ | ✅ | ✅ |
| Packaged score traces | ❌ | Phase 2 | ✅ | ✅ |
| Answers and raw responses | ❌ | ❌ | ❌ | ✅ |
| Frozen numerical references | ❌ | ❌ | ✅ | ✅ |
| Hidden variants and tolerances | ❌ | ❌ | ✅ | ✅ |
| Provider credentials | ❌ | ❌ | ❌ | Session only |

---

## Reward architecture

```mermaid
pie showData
    title Core v1 reward weights
    "Numerical reproduction" : 35
    "Plan + manifest" : 15
    "Ablations" : 15
    "Hidden robustness" : 15
    "Forecast calibration" : 10
    "Report interpretation" : 10
```

| Component | Weight | Evaluation |
|---|---:|---|
| Forecast calibration | 10% | Brier score for binary outcomes; CRPS for continuous predictions |
| Plan + manifest | 15% | Schema, hypotheses, controls, falsification, leakage controls, complete registration |
| Numerical reproduction | 35% | Cell and aggregate values compared with private tolerances |
| Ablations | 15% | Intervention, effect, uncertainty, outcome, and interpretation |
| Hidden robustness | 15% | Deterministic hidden variant selected from the task-instance seed |
| Report interpretation | 10% | Scientific report judged against private result-grounded evidence |

```mermaid
flowchart TD
    X["Agent submission"] --> V{"All required files<br/>valid and regular?"}
    V -- No --> Z["Affected components = 0"]
    V -- Yes --> M["Score public matrix"]
    M --> A{"Numerics and ablations<br/>at least 50%?"}
    A -- No --> CAP["Deterministic reward capped at 0.50"]
    A -- Yes --> H["Copy into read-only<br/>grading tree"]
    H --> U["Run on hidden inputs<br/>with timeout"]
    U --> R["Validate hidden result"]
    R --> J["Judge interpretation"]
```

Controls also include in-memory preregistration hashes, tamper caps, stable hidden selection, rejection of links and oversized files, strict schemas, and process-group termination after a 900-second timeout.

---

## Repository map

```text
.
├── env.py                           # Core lifecycle and phase watcher
├── env_monitoring.py                # Separate regression environment
├── tasks_paper.py                   # Official Core v1 taskset
├── tasks_monitoring.py              # Regression-only taskset
├── Dockerfile.hud                   # Production evaluator image
├── paper_reproduction/
│   ├── MMLU_CORE_V1_PROTOCOL.md     # Pinned external study
│   ├── EXTERNAL_COLLECTION.md       # Collection workflow
│   ├── phase1/                      # Redacted paper + preregistration
│   ├── release/                     # Released only after lock
│   └── vendor/optstop/              # Pinned analysis implementation
├── verifier/
│   ├── optstop_score.py             # Deterministic grader
│   ├── output_validation.py         # Strict schemas
│   ├── preflight_core_package.py    # Deployment gate
│   └── private_optstop/             # Gitignored private bundle
├── scripts/
│   ├── collect_current_model_study.py
│   ├── finalize_core_v1_package.py
│   ├── freeze_optstop_reference.py
│   └── probe_*.py                   # No-cost contract tests
└── sandbox/                         # Restricted submission launcher
```

---

## Source paper → deployable environment

```mermaid
flowchart TD
    PDF["Pinned source PDF"] --> REDACT["Build + validate<br/>redacted paper"]
    DATA["Pinned MMLU snapshot"] --> DEF["Build study definition<br/>and scorer"]
    DEF --> EST["Estimate calls and cost"]
    EST -->|approved| COLLECT["Collect outside HUD"]
    COLLECT --> NORMALIZE["Score + normalize<br/>720 records"]
    NORMALIZE --> FINALIZE["Finalize package"]
    FINALIZE --> PUBLIC["Agent-facing traces"]
    FINALIZE --> FREEZE["20-seed reference freeze"]
    FREEZE --> HIDDEN["7 hidden variants<br/>+ tolerances"]
    REDACT --> STRICT["Strict preflight"]
    PUBLIC --> STRICT
    HIDDEN --> STRICT
    STRICT -->|pass| BUILD["Build HUD image"]
    BUILD --> PILOT["One-model pilot"]
    PILOT --> REVIEW["Inspect transcript,<br/>reward, runtime, failure"]
```

### 1 · Build the redacted paper

```bash
uv run python scripts/build_redacted_optstop_paper.py \
  --source "/secure/source/Knowing When to Stop - Pilditch (2026 arXiv).pdf" \
  --output paper_reproduction/phase1/paper_redacted.md \
  --provenance paper_reproduction/phase1/paper_provenance.json

uv run python scripts/check_optstop_reference.py --phase-one-only
```

The extraction keeps methods, setup, formal Appendix A, limitations, and references while removing answer-bearing claims, results, figures, captions, conclusions, and empirical Appendix B.

### 2 · Build the external study

```bash
hf download cais/mmlu all/test-00000-of-00001.parquet \
  --revision c30699e8356da336a370243923dbaf21066bb9fe \
  --local-dir /secure/mmlu-snapshot

uv run --with pyarrow==17.0.0 python scripts/build_mmlu_core_v1_study.py \
  --mmlu-test-parquet /secure/mmlu-snapshot/all/test-00000-of-00001.parquet \
  --output-definition /secure/external_study/study_definition.json \
  --output-scorer /secure/external_study/scorer.py
```

See the [MMLU Core v1 protocol](paper_reproduction/MMLU_CORE_V1_PROTOCOL.md) for the pinned revision and SHA-256.

### 3 · Estimate before provider calls

> [!CAUTION]
> Collection is a paid external operation. Keep the HUD credential in the collection shell only. Never copy `.env`, responses, answer keys, or a token into Git or the evaluator image.

The collector computes a no-call estimate before execution. Finalization rejects a declared study cost above **$50**, synthetic records, incomplete matrices, invalid scores, and provenance mismatches. See the [external collection workflow](paper_reproduction/EXTERNAL_COLLECTION.md).

### 4 · Finalize the package pair

```bash
uv run python scripts/finalize_core_v1_package.py \
  --input-jsonl /secure/location/scored_traces.jsonl \
  --collection-metadata /secure/location/collection_metadata.json
```

| Output | Contents | Visibility |
|---|---|---|
| Public release data | Validated score traces and manifest | Agent-visible in Phase 2 |
| Private reference bundle | Results, tolerances, hidden variants, judge evidence | Grader only |

Both sides are atomic: failure should not leave a partial package that appears deployable.

### 5 · Review scientific diagnostics

- Reject chains with divergences.
- Inspect effective sample size and convergence diagnostics.
- Verify runtime and seed coverage.
- Independently inspect aggregate decision logic.
- Test whether challenge strata behave as intended.
- Record non-replication rather than “fixing” it away.

---

## Validation ladder

```mermaid
flowchart BT
    A["1 · Contract probes"] --> B["2 · Strict package preflight"]
    B --> C["3 · Production image validation"]
    C --> D["4 · Single hosted pilot"]
    D --> E["5 · Repeated evaluation"]
    E --> F["6 · Benchmark evidence"]
```

| Level | A pass establishes | It does **not** establish |
|---|---|---|
| Contract probes | Interfaces, schemas, packaging, locking | Real collection or scientific validity |
| Strict preflight | Public/private artifacts are consistent | Hosted execution |
| Image validation | Packaging and permissions work | Useful agent behavior |
| Hosted pilot | One trajectory finishes and grades | Reliability or headroom |
| Repeated evaluation | Failure modes and score distribution | Practitioner relevance |
| Benchmark evidence | Reward tracks useful unsaturated skill | Broad generalization |

<details>
<summary><strong>Run all no-cost validation commands</strong></summary>

```bash
uv run python scripts/validate_reference.py
uv run python scripts/probe_controls.py
uv run python scripts/probe_hud_lifecycle.py
uv run python scripts/probe_collector_contract.py
uv run python scripts/probe_trace_packaging.py
uv run python scripts/probe_freeze_bundle.py
uv run python scripts/probe_mmlu_study_builder.py
uv run python scripts/probe_core_image_preflight.py
uv run python scripts/probe_hidden_submission_staging.py
uv run python scripts/probe_output_validation.py
uv run python scripts/probe_phase_release_watcher.py
uv run python scripts/probe_optstop_full_task.py
uv run python scripts/probe_optstop_phase_lock.py
uv run python scripts/check_optstop_reference.py
```

</details>

> [!WARNING]
> Fixture probes are engineering evidence. They do not substitute for the real Bayesian workload, production isolation, hosted execution, transcript review, or expert assessment of the reward.

---

## Deployment

### Readiness gate

- [ ] `paper_reproduction/release/data/manifest.json` exists from real traces
- [ ] `verifier/private_optstop/reference_bundle.json` exists
- [ ] Strict `check_optstop_reference.py` preflight passes
- [ ] Convergence diagnostics have been reviewed
- [ ] No credentials or raw responses are in the build context
- [ ] Production sandbox and numeric UID behavior are validated
- [ ] A one-pilot budget and stopping condition are approved

### Deploy and pilot Core v1

```bash
hud deploy env.py --runtime hud --no-env
hud sync tasks "AI Safety Paper Reproduction - Core v1" tasks_paper.py --dry-run
hud sync tasks "AI Safety Paper Reproduction - Core v1" tasks_paper.py --yes

hud eval "AI Safety Paper Reproduction - Core v1" claude-sonnet-4-6 \
  --remote --all --auto-respond --max-steps 120 \
  --max-concurrent 1 --config max_tokens=4096 --yes
```

Inspect the trajectory, every score component, report-judge evidence, hidden-execution notes, runtime, and spend before repeated runs.

### Deploy regression separately

```bash
hud deploy env_monitoring.py --runtime hud --no-env \
  --build-arg HUD_ENV_MODULE=env_monitoring.py
hud sync tasks "AI Safety Monitoring Regression" tasks_monitoring.py --yes
```

---

## Security model

```mermaid
flowchart TB
    HOST["HUD evaluator host"] --> SERVER["Trusted environment process"]
    HOST --> ROOT["Root-only verifier assets"]
    SERVER --> WS["Agent workspace<br/>UID 65532 · no network"]
    ROOT --> GRADE["Copied read-only<br/>grading workspace"]
    WS -->|regular files only| GRADE
    GRADE --> EXEC["Restricted process<br/>timeout + group kill"]
    style ROOT fill:#7f1d1d,color:#fff
    style WS fill:#1e3a8a,color:#fff
    style GRADE fill:#14532d,color:#fff
```

| Layer | Control |
|---|---|
| Network | Agent workspace declares `network=False` |
| Identity | Numeric unprivileged UID/GID |
| Credentials | Collection-only; excluded from Git and image |
| Hidden data | Root-only verifier directory |
| File transfer | Regular-file-only, no-follow grading copy |
| Execution | Minimal environment, restricted launcher, timeout |
| Cleanup | Dedicated session and process-group termination |
| Phase integrity | Strict schemas, in-memory hashes, atomic release |
| Reward integrity | Hidden matrices, deterministic selection, caps |

The seccomp launcher and numeric UID are defense in depth, not a claim of equivalence to validated bubblewrap or VM isolation.

---

## Known limitations

<details open>
<summary><strong>Scientific limitations</strong></summary>

- MMLU is public and may be present in model training data.
- This tests a stopping procedure on a controlled score matrix, not contamination-free frontier capability.
- Core v1 uses a paired item-level Student-t approximation rather than every hierarchical appendix analysis.
- One paper cannot demonstrate broad automated-research ability.
- A frozen reference is only as trustworthy as its implementation and reviewed diagnostics.

</details>

<details>
<summary><strong>Benchmark limitations</strong></summary>

- Strong-model transcripts and repeated-run failure analysis are still needed.
- Human and expert baselines are needed to establish realism.
- Reward correlation with expert judgment is not yet demonstrated.
- One hidden matrix per instance tests generalization narrowly.
- More papers, non-replications, and known-flaw studies are required for scale.

</details>

<details>
<summary><strong>Claim boundary</strong></summary>

| Level | Establishes | Core v1 |
|---|---|---|
| Synthetic pilot | Executes a method on constructed data | Regression support only |
| Independent redacted-paper reproduction | Runs documented analyses on new clean inputs | **Intended level** |
| Faithful historical replay | Uses original traces or exact models/prompts/scorers | Not claimed |

</details>

---

## Scaling path

```mermaid
flowchart LR
    V1["Core v1<br/>one study"] --> P["Multiple papers"]
    P --> F["Failure library<br/>bugs + overclaims"]
    F --> N["Private novel studies"]
    N --> E["Expert-calibrated suite"]
    E --> RL["RL-ready distribution<br/>measured headroom"]
```

A credible suite should mix solid reproductions, genuine non-replications, known implementation defects, overstated conclusions, private studies with lower leakage, and tasks where honest uncertainty is more valuable than experimental success.

The target skill is not “always confirm the paper.” It is **produce trustworthy research under uncertainty**.

---

## Design documents

- [Benchmark contract](analysis/PAPER_REPRODUCTION_CONTRACT.md)
- [MMLU Core v1 protocol](paper_reproduction/MMLU_CORE_V1_PROTOCOL.md)
- [External collection workflow](paper_reproduction/EXTERNAL_COLLECTION.md)
- [Phase-one agent task](paper_reproduction/phase1/task.md)
- [HUD pilot plan](analysis/HUD_PILOT_PLAN.md)
- [Validation notes](analysis/VALIDATION.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

---

## Responsible use

This repository is for controlled AI-safety evaluation and research. Never place production credentials, raw responses, answer keys, private references, or non-public paper materials in Git history. Treat agent-generated conclusions as experimental results requiring independent verification—not authoritative research findings.
