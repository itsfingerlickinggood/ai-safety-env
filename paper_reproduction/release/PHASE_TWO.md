# Phase-two execution requirements

This material appears under `phase_two/`. Read `phase_two/analysis_manifest.json`
and `phase_two/data/manifest.json`. Use `phase_two/run_analysis.py`
or the pinned vendor implementation for all nine cells. Network access is
disabled and no model calls are permitted inside this environment.

`core_parameters.json` is the registered baseline configuration used for the
nine core cells; `run_analysis.py` uses it by default. For the item-order
ablation, pass `--no-shuffle-items`. For the conservatism ablation, copy the
configuration, change only `conservatism` from `5` to `8`, and pass that copy
with `--params`. The fixed-budget baseline retains all four epochs without
calling the stopping rule. These controls are methodological inputs, not
answer-bearing reference results.

For the overall equivalence conclusion, combine the nine registered cell-level
decisions: report `reject` if any cell rejects equivalence, `accept_null` only
if every cell accepts it, and otherwise report `undecided`. Do not replace
this uncertainty rule with a threshold on raw mean differences.

Run the registered ablations exactly as specified in `ablation_protocol.json`.

Write these final artifacts:

- `reproduction_results.json`, conforming exactly to `reproduction_results.schema.json`, with all nine `cells`,
  `mean_efficiency`, `mean_absolute_difference`, and an
  `overall_equivalence_decision`. Every cell records `efficiency`,
  `full_mean`, `retained_mean`, `absolute_difference`,
  `paired_n`, `paired_mean_difference`, `paired_hdi_94`, `rope`,
  `equivalence_decision`, and `error`. The paired 94% interval is evaluated
  against a ROPE of 0.02 for binary/continuous cells and 0.01 for normalised
  ordinal cells. Core v1 uses a deterministic paired Student-t posterior
  approximation for this bounded comparison; it does not claim to reproduce
  the paper's full appendix-level hierarchical equivalence suite.
- `ablations.json`, conforming exactly to `ablations.schema.json`, with entries for
  `fixed_budget_baseline`, `item_order_sensitivity`, and
  `stopping_conservatism_sensitivity`. Each entry requires the exact registered
  `changed_parameter`, a finite `effect_size`, finite non-negative
  `uncertainty`, `outcome` (`stable` or `sensitive`), and `interpretation`.
- `submission.py`, accepting `--input-dir INPUT --output OUTPUT`, which emits
  `submission_result.schema.json` for any manifest-compatible matrix.
- `final_report.md`, separating methods, results, ablations, uncertainty,
  limitations, and an explicit supported/insufficient/not-supported decision.

Do not alter `forecast.json`. A valid result may be a non-replication.
