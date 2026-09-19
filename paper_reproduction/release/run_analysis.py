"""Workspace-local optstop entry point used by the phase-two task.

It makes the vendored package importable without depending on an agent-set
``PYTHONPATH``. The agent may inspect and extend this wrapper, but submitted
analyses must retain the documented CSV input interface.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import t as student_t


ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))


def _paired_equivalence(full: pd.DataFrame, retained: pd.DataFrame, score_type: str) -> dict[str, object]:
    denominator = 10.0 if score_type == "ordinal" else 1.0
    full_by_item = full.groupby("item_id", sort=False).score.mean() / denominator
    retained_by_item = retained.groupby("item_id", sort=False).score.mean() / denominator
    common = full_by_item.index.intersection(retained_by_item.index)
    rope = 0.01 if score_type == "ordinal" else 0.02
    if len(common) < 2:
        return {"paired_n": int(len(common)), "paired_mean_difference": 0.0, "paired_hdi_94": [0.0, 0.0], "rope": rope, "equivalence_decision": "undecided", "paired_error": "fewer than two paired items after stopping"}
    differences = (full_by_item.loc[common] - retained_by_item.loc[common]).to_numpy(dtype=float)
    mean = float(differences.mean())
    standard_deviation = float(differences.std(ddof=1))
    if standard_deviation == 0.0:
        lower = upper = mean
    else:
        scale = standard_deviation / math.sqrt(len(differences))
        lower, upper = (float(student_t.ppf(probability, df=len(differences) - 1, loc=mean, scale=scale)) for probability in (0.03, 0.97))
    if lower >= -rope and upper <= rope:
        decision = "accept_null"
    elif lower > rope or upper < -rope:
        decision = "reject"
    else:
        decision = "undecided"
    return {"paired_n": int(len(differences)), "paired_mean_difference": mean, "paired_hdi_94": [lower, upper], "rope": rope, "equivalence_decision": decision, "paired_error": None}


def aggregate_equivalence(cells: dict[str, dict[str, object]]) -> str:
    """Apply the registered cell-level uncertainty rule to the whole matrix."""
    decisions = [str(cell["equivalence_decision"]) for cell in cells.values()]
    if any(decision == "reject" for decision in decisions):
        return "reject"
    if decisions and all(decision == "accept_null" for decision in decisions):
        return "accept_null"
    return "undecided"


def analyze_cell(path: Path, params: dict[str, object], *, shuffle_items: bool = True) -> dict[str, object]:
    from optstop import optimal_stopping_posthoc

    data = pd.read_csv(path)
    score_type = str(data.score_type.iloc[0])
    run_params = dict(params)
    ordinal_max_score = 10
    if score_type == "ordinal" and "ordinal_max_score" in data and pd.notna(data.ordinal_max_score.iloc[0]):
        ordinal_max_score = int(data.ordinal_max_score.iloc[0])
    run_params.update(
        {
            "ordinal_tasks": ["ordinal"],
            "continuous_tasks": ["continuous"],
            "ordinal_max_score": ordinal_max_score,
        }
    )
    pruned, summary = optimal_stopping_posthoc(
        data,
        params=run_params,
        grouping_columns=["regime", "score_type"],
        sample_id_column="item_id",
        epoch_column="epoch",
        score_column="score",
        display_progress=False,
        ordinal_tasks=["ordinal"],
        ordinal_max_score=run_params["ordinal_max_score"],
        continuous_tasks=["continuous"],
        processing_order="epoch_interleaved",
        reanalysis_interval=int(run_params.get("reanalysis_interval", 2)),
        max_workers=1,
        shuffle_items=shuffle_items,
        shuffle_seed=int(run_params.get("random_seed", 42)),
    )
    denominator = float(run_params["ordinal_max_score"]) if score_type == "ordinal" else 1.0
    full_mean = float(data.score.mean() / denominator)
    retained_mean = float(pruned.score.mean() / denominator) if not pruned.empty else full_mean
    entry = summary[0] if summary else {}
    paired = _paired_equivalence(data, pruned, score_type)
    return {
        "efficiency": 1.0 - float(entry.get("percent_items_used") or 1.0),
        "full_mean": full_mean,
        "retained_mean": retained_mean,
        "absolute_difference": abs(full_mean - retained_mean),
        **{key: value for key, value in paired.items() if key != "paired_error"},
        "error": entry.get("error") or paired["paired_error"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--params", type=Path, default=ROOT / "core_parameters.json",
        help="JSON analysis configuration; defaults to the registered Core v1 parameters",
    )
    parser.add_argument(
        "--shuffle-items", action=argparse.BooleanOptionalAction, default=True,
        help="enable the registered shuffled-item order (use --no-shuffle-items for its ablation)",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze_cell(args.input, json.loads(args.params.read_text()), shuffle_items=args.shuffle_items)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
