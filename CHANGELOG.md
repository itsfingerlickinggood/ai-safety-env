# Changelog

## 0.2.0 — long-horizon redesign

- Replaced the one-formula synthetic CSV task with a complete forecast → design → reproduce → probe → generalize → interpret workflow.
- Grounded the research question in ResearchArena while preserving an explicit scoped-analogue claim boundary.
- Added 48 deterministic public trajectory/artifact cases and 76 hidden calibration/test cases materialized per run.
- Held out cross-lingual, fragmented-state, contamination, and evaluator-tampering mechanisms from public data.
- Added executable normal/trigger/counterfactual artifact probes and benign security decoys.
- Expanded the agent contract to six auditable deliverables.
- Added forecast, design, public-reproduction, ablation, hidden-quality, baseline-delta, FPR, family-recall, evidence, and conclusion subscores.
- Added strict output validation and an always-benign performance gate.
- Required hosted workspace isolation in the deployed image and retained a separate submission sandbox.
- Increased the task budget to 220 steps and two hours.
- Added real `hud==0.6.15` lifecycle validation, adversarial controls, provenance, failure taxonomy, and pilot requirements.
