"""No-cost negative controls for strict Core v1 artifact validation."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from verifier.output_validation import (  # noqa: E402
    ABLATIONS,
    CELLS,
    FORECAST_BINARY,
    FORECAST_CONTINUOUS,
    valid_ablations,
    valid_forecast,
    valid_reproduction_results,
    valid_report,
)
from scripts.freeze_optstop_reference import _paired_equivalence  # noqa: E402
from verifier.optstop_score import _forecast_score  # noqa: E402


def main() -> None:
    for path in (
        REPO / "paper_reproduction" / "phase1" / "forecast.schema.json",
        REPO / "paper_reproduction" / "phase1" / "experiment_plan.schema.json",
        REPO / "paper_reproduction" / "release" / "reproduction_results.schema.json",
        REPO / "paper_reproduction" / "release" / "ablations.schema.json",
        REPO / "paper_reproduction" / "release" / "submission_result.schema.json",
    ):
        schema = json.loads(path.read_text())
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    forecast = {
        "schema_version": 1,
        "binary": [{"id": identifier, "probability": 0.5} for identifier in sorted(FORECAST_BINARY)],
        "continuous": [{"id": identifier, "mean": 0.5, "std": 0.1} for identifier in sorted(FORECAST_CONTINUOUS)],
    }
    result = {
        "schema_version": 1,
        "cells": {
            identifier: {
                "efficiency": 0.4, "full_mean": 0.5, "retained_mean": 0.5,
                "absolute_difference": 0.0, "paired_n": 20, "paired_mean_difference": 0.0,
                "paired_hdi_94": [-0.01, 0.01], "rope": 0.02,
                "equivalence_decision": "accept_null", "error": None,
            }
            for identifier in CELLS
        },
        "mean_efficiency": 0.4,
        "mean_absolute_difference": 0.0,
        "overall_equivalence_decision": "accept_null",
    }
    ablations = {
        "schema_version": 1,
        "ablations": [
            {"id": identifier, "changed_parameter": "registered change", "effect_size": 0.1, "uncertainty": 0.01, "outcome": "sensitive", "interpretation": "Interpret this registered change."}
            for identifier in sorted(ABLATIONS)
        ],
    }
    assert valid_forecast(forecast)
    assert valid_reproduction_results(result)
    assert valid_ablations(ablations)
    assert valid_report("Methods\n" + "results ablations uncertainty limitations " * 30)
    duplicate = copy.deepcopy(forecast)
    duplicate["binary"][1]["id"] = duplicate["binary"][0]["id"]
    malformed = copy.deepcopy(result)
    malformed["cells"]["low_binary"].pop("error")
    extra = copy.deepcopy(ablations)
    extra["ablations"][0]["fabricated"] = True
    assert not valid_forecast(duplicate)
    assert not valid_reproduction_results(malformed)
    assert not valid_ablations(extra)
    full = pd.DataFrame({"item_id": ["a", "a", "b", "b"], "score": [1.0, 1.0, 1.0, 1.0]})
    same = _paired_equivalence(full, full, "binary")
    shifted = _paired_equivalence(full, pd.DataFrame({"item_id": ["a", "b"], "score": [0.8, 0.8]}), "binary")
    assert same["equivalence_decision"] == "accept_null"
    assert shifted["equivalence_decision"] == "reject"
    forecast_bundle = {
        "forecast_outcomes": {
            "binary": {identifier: False for identifier in FORECAST_BINARY},
            "continuous": {"mean_efficiency": 0.4, "mean_absolute_difference": 0.0},
        }
    }
    poor = copy.deepcopy(forecast)
    poor["continuous"] = [
        {"id": "mean_efficiency", "mean": 0.2, "std": 0.3},
        {"id": "mean_absolute_difference", "mean": 0.2, "std": 0.3},
    ]
    accurate = copy.deepcopy(forecast)
    accurate["binary"] = [{"id": identifier, "probability": 0.0} for identifier in FORECAST_BINARY]
    accurate["continuous"] = [
        {"id": "mean_efficiency", "mean": 0.4, "std": 0.05},
        {"id": "mean_absolute_difference", "mean": 0.0, "std": 0.05},
    ]
    with tempfile.TemporaryDirectory(prefix="forecast-score-") as raw:
        root = Path(raw)
        (root / "forecast.json").write_text(json.dumps(poor))
        poor_score = _forecast_score(root, forecast_bundle)
        (root / "forecast.json").write_text(json.dumps(accurate))
        accurate_score = _forecast_score(root, forecast_bundle)
    assert 0.0 <= poor_score < accurate_score < 1.0
    print('{"output_validation": "passed", "duplicate_forecast_rejected": true, "malformed_result_rejected": true, "extra_ablation_field_rejected": true, "paired_rope_accept_and_reject_checked": true, "forecast_calibration_checked": true}')


if __name__ == "__main__":
    main()
