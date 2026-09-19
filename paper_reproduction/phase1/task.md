# optstop Core Reproduction v1 - phase 1: preregistration

You are reproducing the central 3x3 study from *Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations*.

This is a bounded **independent reproduction** using a new, provenance-recorded current-model study. It is not an exact replay of the authors' historical model runs and it does not claim to reproduce every appendix analysis.

Read `paper_redacted.md`, `paper_provenance.json`, `RESEARCH_PROTOCOL.md`, and
`experiment_plan.schema.json`. Before any experimental inputs are released,
create both files below:

1. `forecast.json`: calibrated forecasts for the registered primary outcomes and sensitivity/non-replication outcomes. Follow `forecast.schema.json` exactly.
2. `experiment_plan.json`: the research question, hypotheses, data mapping, fixed parameters, controls, all registered ablations, falsification criteria, leakage controls, and an analysis plan for every manifest entry.

The trusted environment validates and hashes `forecast.json` after this phase.
Experimental traces, the runnable package, and phase-two instructions are
released only after both phase-one files are valid. **Do not end the task after
writing them.** Wait until `PHASE_TWO_READY` appears in the workspace, then
read the released `phase_two/` directory and complete phase two in the same
shell session. Do not alter either preregistration artifact after release.

`experiment_plan.json` must set `schema_version` to `1` and include
`research_question`, `hypotheses`, `data_mapping`, `parameters`, `controls`,
`ablations`, `falsification_criteria`, `leakage_controls`, `analysis_plan`,
and `analysis_manifest`. The latter must list every identifier in the supplied
plan schema. State the registered practical-equivalence/ROPE criterion and how
you will handle non-convergence and non-replication.

Use this exact forecast shape:

```json
{
  "schema_version": 1,
  "binary": [
    {"id": "mean_efficiency_above_50pct", "probability": 0.5},
    {"id": "any_condition_above_90pct", "probability": 0.5},
    {"id": "all_conditions_equivalent", "probability": 0.5},
    {"id": "nonreplication_possible", "probability": 0.5}
  ],
  "continuous": [
    {"id": "mean_efficiency", "mean": 0.5, "std": 0.2},
    {"id": "mean_absolute_difference", "mean": 0.02, "std": 0.02}
  ]
}
```
