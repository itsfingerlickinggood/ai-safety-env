"""No-cost contract test for the Core v1 preregistration gate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from env import FORECAST_TAMPER_REWARD_CAP, _apply_reward_caps, _valid_phase_one_forecast, _valid_phase_one_plan


FORECAST = {
    "schema_version": 1,
    "binary": [
        {"id": "mean_efficiency_above_50pct", "probability": 0.5},
        {"id": "any_condition_above_90pct", "probability": 0.5},
        {"id": "all_conditions_equivalent", "probability": 0.5},
        {"id": "nonreplication_possible", "probability": 0.5},
    ],
    "continuous": [
        {"id": "mean_efficiency", "mean": 0.5, "std": 0.2},
        {"id": "mean_absolute_difference", "mean": 0.02, "std": 0.02},
    ],
}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="optstop-phase-lock-") as raw:
        root = Path(raw)
        forecast = root / "forecast.json"
        plan = root / "experiment_plan.json"
        forecast.write_text("{}")
        if _valid_phase_one_forecast(forecast):
            raise SystemExit("malformed forecast unexpectedly passed")
        forecast.write_text(json.dumps(FORECAST))
        plan.write_text(json.dumps({"schema_version": 1, "analysis_manifest": []}))
        if _valid_phase_one_plan(plan):
            raise SystemExit("incomplete plan unexpectedly passed")
        identifiers = [
            "low_binary", "mid_binary", "high_binary", "low_ordinal", "mid_ordinal", "high_ordinal",
            "low_continuous", "mid_continuous", "high_continuous", "fixed_budget_baseline",
            "item_order_sensitivity", "stopping_conservatism_sensitivity",
        ]
        plan.write_text(json.dumps({
            "schema_version": 1,
            "research_question": "Can the fixed offline score traces support a bounded independent reproduction?",
            "hypotheses": ["efficiency", "equivalence", "sensitivity"],
            "data_mapping": ["map every registered cell to the released score trace"], "parameters": {"rope": 0.02}, "controls": ["seed", "order", "fixed budget"],
            "ablations": ["fixed", "order", "conservatism"],
            "falsification_criteria": ["non-convergence", "large difference"],
            "leakage_controls": ["forecast first"], "analysis_plan": ["run every registered analysis"], "analysis_manifest": identifiers,
        }))
        if not (_valid_phase_one_forecast(forecast) and _valid_phase_one_plan(plan)):
            raise SystemExit("valid preregistration unexpectedly failed")
    tamper_context: dict[str, object] = {"notes": []}
    if _apply_reward_caps(1.0, tamper_context, forecast_locked=False, plan_locked=True) != FORECAST_TAMPER_REWARD_CAP:
        raise SystemExit("modified forecast did not trigger the integrity cap")
    if not tamper_context["notes"]:
        raise SystemExit("modified forecast did not leave an audit note")
    plan_tamper_context: dict[str, object] = {"notes": []}
    if _apply_reward_caps(1.0, plan_tamper_context, forecast_locked=True, plan_locked=False) != FORECAST_TAMPER_REWARD_CAP:
        raise SystemExit("modified experiment plan did not trigger the integrity cap")
    if not plan_tamper_context["notes"]:
        raise SystemExit("modified experiment plan did not leave an audit note")
    print(json.dumps({"phase_lock": "passed", "invalid_forecast_rejected": True, "incomplete_plan_rejected": True, "forecast_tamper_capped": True, "plan_tamper_capped": True}))


if __name__ == "__main__":
    main()
