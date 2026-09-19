# Redacted-Paper Reproduction Benchmark Contract

## The task we are building

The agent receives a full AI-safety paper with all answer-bearing results removed.  It must forecast the outcome before running any analysis, reproduce the experiments using supplied offline materials, run the paper's registered ablations, and state whether the evidence supports, is insufficient for, or fails to support the paper's claims.

This is **not** a paper-summary task and it is **not** a task in which the agent is expected to guess missing methods.  The long horizon comes from doing real research work: reading, forecasting, planning, executing, debugging, analysing, ablating, and reporting.

## What the agent sees

The following must be visible in the agent workspace:

- a source-derived redacted paper package with answer-bearing passages replaced by `[RESULTS REDACTED]`;
- methods, experimental setup, dataset identities, metrics, analysis protocol, and limitations;
- clean, non-answer-bearing experiment inputs in a documented offline format;
- pinned source code and dependencies needed to execute the analyses;
- an analysis manifest listing every main analysis and required ablation;
- output schemas and a writable workspace.

The reproducibility inputs are not answers.  They are the laboratory materials that make an independent reproduction possible.  They must therefore remain available to the agent.

## What remains hidden

The following must never appear in the agent workspace or image layers readable by the agent:

- the paper's result and conclusion text;
- result-bearing tables, figures, captions, and appendix summaries;
- original or frozen aggregate outputs;
- generated result figures and logs that reveal outcomes;
- hidden test inputs and labels;
- numerical tolerances, reference artifacts, and verifier source;
- provider credentials.

## Required agent workflow

1. Read the redacted paper and analysis manifest.
2. Write and freeze `forecast.json` before execution.
3. Write `experiment_plan.json` mapping each registered paper analysis to a runnable step.
4. Execute every required analysis and ablation on the supplied inputs.
5. Write `reproduction_results.json`, `ablations.json`, and `final_report.md`.
6. The report must distinguish: replication supported, evidence insufficient, and claim not supported.

## Honest names for three benchmark levels

| Name | What it establishes |
|---|---|
| `synthetic/reconstructed optstop pilot` | Agent can execute a method on constructed data and generalize to held-out synthetic variants. |
| `independent redacted-paper reproduction` | Agent can independently run the paper's documented analyses on clean supplied inputs and determine the outcome. |
| `faithful replay of the original paper run` | In addition, exact original item-by-epoch traces or a regeneration using the original models, prompts, scorers, and versions are available. |

Core v1 is designed to be the second level: a bounded independent
redacted-paper reproduction. It does not claim a historical replay because the
authors' original item-by-epoch traces are unavailable. Its current-model
score-trace package and private reference bundle must be generated and
validated before it is deployable.

## Core v1 implementation gate

Core v1 implements the level-two architecture: a source-derived redacted
paper, a visible nine-cell/three-ablation manifest, a current-model trace
packaging gate, and a private frozen-reference grader. Keep the synthetic
monitoring task as a fast regression test.

It becomes deployable only after provenance-verified clean score traces and
the private reference bundle are built. Until then, its intentional fail-closed
state prevents a misleading synthetic or partial rollout.

Exact original traces are desirable but not a prerequisite for this level.  If they are unavailable, the task must compare the agent against a newly frozen reference run and report itself as an independent reproduction rather than an exact historical replay.

## Shipping gate

Do not call the task a paper-reproduction benchmark until all of these are true:

- the agent-facing paper is complete except for answer-bearing content;
- every required analysis appears in the visible manifest;
- supplied inputs can actually execute the required analyses offline;
- reference outputs are generated from the pinned implementation and kept hidden;
- the grader verifies execution, manifest completeness, numerical outputs, and honest scientific interpretation;
- hidden variants reject hardcoded public results;
- the current synthetic task still passes its deterministic regression checks.
