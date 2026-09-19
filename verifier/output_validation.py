"""Strict, dependency-free validation for every Core v1 agent artifact."""

from __future__ import annotations

import math
from typing import Any


CELLS = {
    f"{regime}_{score_type}"
    for regime in ("low", "mid", "high")
    for score_type in ("binary", "ordinal", "continuous")
}
ABLATIONS = {
    "fixed_budget_baseline", "item_order_sensitivity", "stopping_conservatism_sensitivity",
}
FORECAST_BINARY = {
    "mean_efficiency_above_50pct", "any_condition_above_90pct",
    "all_conditions_equivalent", "nonreplication_possible",
}
FORECAST_CONTINUOUS = {"mean_efficiency", "mean_absolute_difference"}
PLAN_KEYS = {
    "schema_version", "research_question", "hypotheses", "data_mapping", "parameters", "controls",
    "ablations", "falsification_criteria", "leakage_controls", "analysis_plan", "analysis_manifest",
}
RESULT_KEYS = {
    "schema_version", "cells", "mean_efficiency", "mean_absolute_difference", "overall_equivalence_decision",
}
CELL_RESULT_KEYS = {
    "efficiency", "full_mean", "retained_mean", "absolute_difference", "paired_n",
    "paired_mean_difference", "paired_hdi_94", "rope", "equivalence_decision", "error",
}
ABLATION_ENTRY_KEYS = {"id", "changed_parameter", "effect_size", "uncertainty", "outcome", "interpretation"}
DECISIONS = {"accept_null", "undecided", "reject"}


def _number(value: Any, *, minimum: float | None = None, maximum: float | None = None, positive: bool = False) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return (
        math.isfinite(number)
        and (minimum is None or number >= minimum)
        and (maximum is None or number <= maximum)
        and (not positive or number > 0)
    )


def valid_forecast(payload: Any) -> bool:
    try:
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "binary", "continuous"} or payload["schema_version"] != 1:
            return False
        binary = payload["binary"]
        continuous = payload["continuous"]
        if not isinstance(binary, list) or not isinstance(continuous, list) or len(binary) != len(FORECAST_BINARY) or len(continuous) != len(FORECAST_CONTINUOUS):
            return False
        binary_values = {}
        for entry in binary:
            if not isinstance(entry, dict) or set(entry) != {"id", "probability"}:
                return False
            binary_values[str(entry["id"])] = entry["probability"]
        continuous_values = {}
        for entry in continuous:
            if not isinstance(entry, dict) or set(entry) != {"id", "mean", "std"}:
                return False
            continuous_values[str(entry["id"])] = (entry["mean"], entry["std"])
        return (
            set(binary_values) == FORECAST_BINARY
            and set(continuous_values) == FORECAST_CONTINUOUS
            and all(_number(value, minimum=0.0, maximum=1.0) for value in binary_values.values())
            and all(_number(mean) and _number(std, positive=True) for mean, std in continuous_values.values())
        )
    except (KeyError, TypeError):
        return False


def valid_plan(payload: Any) -> bool:
    try:
        if not isinstance(payload, dict) or set(payload) != PLAN_KEYS or payload["schema_version"] != 1:
            return False
        list_keys = {"hypotheses", "data_mapping", "controls", "ablations", "falsification_criteria", "leakage_controls", "analysis_plan", "analysis_manifest"}
        if any(not isinstance(payload[key], list) for key in list_keys) or not isinstance(payload["parameters"], dict):
            return False
        return (
            isinstance(payload["research_question"], str) and len(payload["research_question"].strip()) >= 40
            and len(payload["hypotheses"]) >= 3
            and len(payload["data_mapping"]) >= 1
            and bool(payload["parameters"])
            and len(payload["controls"]) >= 3
            and len(payload["ablations"]) >= 3
            and len(payload["falsification_criteria"]) >= 2
            and len(payload["leakage_controls"]) >= 1
            and len(payload["analysis_plan"]) >= 1
            and set(map(str, payload["analysis_manifest"])) == CELLS | ABLATIONS
            and len(payload["analysis_manifest"]) == len(CELLS | ABLATIONS)
        )
    except (KeyError, TypeError):
        return False


def valid_reproduction_results(payload: Any) -> bool:
    try:
        if not isinstance(payload, dict) or set(payload) != RESULT_KEYS or payload["schema_version"] != 1:
            return False
        cells = payload["cells"]
        if not isinstance(cells, dict) or set(cells) != CELLS:
            return False
        for value in cells.values():
            if not isinstance(value, dict) or set(value) != CELL_RESULT_KEYS:
                return False
            if not all(_number(value[key], minimum=0.0, maximum=1.0) for key in ("efficiency", "full_mean", "retained_mean", "absolute_difference")):
                return False
            if not isinstance(value["paired_n"], int) or value["paired_n"] < 0:
                return False
            if not _number(value["paired_mean_difference"], minimum=-1.0, maximum=1.0) or not _number(value["rope"], minimum=0.0, maximum=1.0, positive=True):
                return False
            if not isinstance(value["paired_hdi_94"], list) or len(value["paired_hdi_94"]) != 2 or not all(_number(bound, minimum=-1.0, maximum=1.0) for bound in value["paired_hdi_94"]):
                return False
            if float(value["paired_hdi_94"][0]) > float(value["paired_hdi_94"][1]):
                return False
            if value["equivalence_decision"] not in DECISIONS or value["error"] is not None and not isinstance(value["error"], str):
                return False
        return (
            _number(payload["mean_efficiency"], minimum=0.0, maximum=1.0)
            and _number(payload["mean_absolute_difference"], minimum=0.0, maximum=1.0)
            and payload["overall_equivalence_decision"] in DECISIONS
        )
    except (KeyError, TypeError):
        return False


def valid_ablations(payload: Any) -> bool:
    try:
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "ablations"} or payload["schema_version"] != 1:
            return False
        entries = payload["ablations"]
        if not isinstance(entries, list) or len(entries) != len(ABLATIONS):
            return False
        by_id = {}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != ABLATION_ENTRY_KEYS:
                return False
            by_id[str(entry["id"])] = entry
        return (
            set(by_id) == ABLATIONS
            and all(_number(entry["effect_size"], minimum=0.0) and _number(entry["uncertainty"], minimum=0.0) for entry in by_id.values())
            and all(entry["outcome"] in {"stable", "sensitive"} and isinstance(entry["changed_parameter"], str) and bool(entry["changed_parameter"].strip()) and isinstance(entry["interpretation"], str) and bool(entry["interpretation"].strip()) for entry in by_id.values())
        )
    except (KeyError, TypeError):
        return False


def valid_report(text: str) -> bool:
    lowered = text.lower()
    return len(text.strip()) >= 500 and all(section in lowered for section in ("method", "result", "ablation", "uncertainty", "limitation"))
