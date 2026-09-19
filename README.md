# HUD AI-Safety Paper Reproduction

This repository contains two deliberately separate HUD tasksets:

- **AI Safety Paper Reproduction - Core v1** is the official target. It asks an
  agent to forecast, reproduce, ablate, and interpret the central 3x3 study
  from *Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations*.
- **AI Safety Monitoring Regression** is the existing synthetic
  sabotage-monitoring task. It remains a deterministic regression check and
  is not part of the paper-reproduction score.

## Claim boundary

Core v1 is a **bounded independent reproduction**. The agent receives a
source-derived redacted paper package: the main methods and formal Appendix A
are retained, while answer-bearing results and empirical Appendix B are
withheld. It also receives clean offline score traces from a newly collected
current-model study, pinned analysis code, and a manifest of the nine core
analyses plus three ablations. It does not claim to replay the authors' original
model calls or every analysis in the original paper.

The public repository intentionally contains no real score traces, frozen
references, provider credentials, result figures, or hidden test cases. Until
the trace collection and reference-freezing steps below are complete, the
paper task fails closed and must not be deployed.

## Build the paper package

The pinned upstream paper PDF is an external source artifact. Build the
agent-facing extraction locally:

```bash
uv run python scripts/build_redacted_optstop_paper.py \
  --source "/path/to/Knowing When to Stop - Pilditch (2026 arXiv).pdf" \
  --output paper_reproduction/phase1/paper_redacted.md \
  --provenance paper_reproduction/phase1/paper_provenance.json
uv run python scripts/check_optstop_reference.py --phase-one-only
```

The extraction preserves the main methods, setup, formal Appendix A material,
limitations, and references. It redacts the abstract outcome claim, main
empirical results, result figures, conclusions, and the whole empirical
Appendix B because it interleaves methods with answer-bearing validation.

## Create the private study package

Generate the current-model traces outside HUD with `claude-sonnet-4-6` using
the pinned MMLU study defined in `paper_reproduction/MMLU_CORE_V1_PROTOCOL.md`.
Keep API keys, answer keys, and raw response text outside this repository.
The collection process computes a conservative cost estimate before making
calls and emits normalized JSONL. By default it uses HUD's
Anthropic-compatible inference gateway with `HUD_API_KEY`, only in the
external collection shell; that credential is never copied into the image.
Then run the single no-secret finalization command:

```bash
uv run python scripts/finalize_core_v1_package.py \
  --input-jsonl /secure/location/scored_traces.jsonl \
  --collection-metadata /secure/location/collection_metadata.json
```

It reads the computed estimate from the collector metadata, requires exactly
20 fixed items x 4 epochs in every one of
the nine cells. The preparation script rejects a study over $50 or any
synthetic/incomplete schema. The reference-freezing script runs the expensive
Bayesian analyses across 20 inference seeds once; it produces hidden variants,
tolerances, and report-judge evidence under `verifier/private_optstop/`, which
is ignored by Git but included in a local Docker build. Both public trace
packaging and private freezing are atomic: a failed operation leaves no partial
artifact that would block a safe retry. The image fails closed unless that
private bundle matches the packaged public traces.

Reference freezing is not evidence of MCMC convergence by itself. Before a
HUD deployment, inspect the recorded runtime and diagnostic output from the
real run and reject the bundle if any chain has divergences, inadequate ESS, or
unavailable/misleading convergence diagnostics. The bounded Core v1
configuration is a runtime feasibility setting, not a claim that one short
chain is sufficient for scientific inference.

Use `paper_reproduction/collection_metadata.example.json` as the metadata
shape. It records exact prompt hashes/locations, scoring settings, model ID,
seed, and collection timestamp without copying raw model completions into the
repository.

## Validation

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

The first two commands validate the retained monitoring regression task. The
third validates its local HUD lifecycle without production UID ownership. The
next ten are no-cost Core v1 contracts for collection, trace packaging,
reference-bundle structure, concrete external-study construction, image-package
integrity, hidden-submission staging, strict output validation, trusted phase release, end-to-end template grading, and preregistration locking. The final command is the strict
paper-task preflight and succeeds only after the private package has been built
from real traces.

## Deploy and pilot

Never load `.env` into the build image. After all validation succeeds:

```bash
hud deploy env.py --runtime hud --no-env
hud sync tasks "AI Safety Paper Reproduction - Core v1" tasks_paper.py --dry-run
hud sync tasks "AI Safety Paper Reproduction - Core v1" tasks_paper.py --yes
hud eval "AI Safety Paper Reproduction - Core v1" claude-sonnet-4-6 \
  --remote --all --auto-respond --max-steps 120 \
  --max-concurrent 1 --config max_tokens=4096 --yes
```

Inspect the trace, the deterministic score, the LLM report-judge result, the
runtime, and spend before running five independent attempts.

The regression environment is deployed separately only when it needs a hosted
regression check:

```bash
hud deploy env_monitoring.py --runtime hud --no-env \
  --build-arg HUD_ENV_MODULE=env_monitoring.py
hud sync tasks "AI Safety Monitoring Regression" tasks_monitoring.py --yes
```

## Security model

The agent workspace has no network or provider credentials. The production
image uses a numeric unprivileged UID, `setpriv`, and a seccomp launcher;
this is a defense-in-depth fallback, not equivalent to bubblewrap isolation.
Verifier source, hidden references, and hidden inputs are root-only. The
grader runs a copied, link-free submission workspace with a separate resource
limit and checks generic behavior on one hidden matrix.

Core v1 is a one-prompt/one-grade HUD task. Within that single agent session,
a trusted server-side watcher releases phase two after valid `forecast.json`
and `experiment_plan.json` files appear. The agent must wait for
`PHASE_TWO_READY`; ending the task before it appears receives zero reward.
