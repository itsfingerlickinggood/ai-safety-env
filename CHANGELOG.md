# Changelog

## 0.3.0 — optstop Core Reproduction v1

- Split the synthetic monitoring regression taskset from the official paper-reproduction taskset.
- Added a source-derived redacted paper extraction, paper provenance, preregistration phase, and phase-two release boundary.
- Replaced the active synthetic optstop CSV generator with a guarded current-model trace-packaging pipeline.
- Added a private 20-seed reference-freezing tool, hidden matrix variants, empirical tolerance bundle, and privileged LLM report judge.
- Made Python 3.12 and the optstop dependency family explicit, and removed Docker's independent unpinned dependency resolution.
- Raised the bounded research-shell limit while retaining a separate submission-runner cap.
- Added strict fail-closed checks for missing trace/reference assets, result leakage, and local non-root lifecycle handling.

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
