"""Freeze private references for optstop Core Reproduction v1.

Run this only after ``prepare_current_model_study.py`` creates the real trace
package. It performs the expensive Bayesian work once, records variation across
20 inference seeds, and writes private artifacts that must never be committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import secrets
import shutil
import sys
import time
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import t as student_t


REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "paper_reproduction" / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

CELLS = tuple(f"{regime}_{score_type}" for score_type in ("binary", "ordinal", "continuous") for regime in ("low", "mid", "high"))
SEEDS = tuple(range(1000, 1020))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _params(seed: int) -> dict[str, object]:
    return {
        "delta_item": 0.05,
        "delta_cap": 0.05,
        "CI_delta": 0.001,
        "cred_level": 0.97,
        "conservatism": 5,
        "draws": 250,
        "tune": 250,
        "chains": 1,
        "cores": 1,
        "random_seed": seed,
        "reanalysis_interval": 2,
        "ordinal_tasks": ["ordinal"],
        "continuous_tasks": ["continuous"],
        "ordinal_max_score": 10,
    }


def _paired_equivalence(full: pd.DataFrame, retained: pd.DataFrame, score_type: str) -> dict[str, object]:
    """Paired 94% Student-t posterior approximation for truncation effects.

    The score traces are paired by item ID, so this compares the full-run and
    retained-run item means rather than applying a threshold to two unrelated
    aggregate means. With the standard weak-prior Normal model this is the
    closed-form posterior for the paired mean difference and is deterministic.
    """
    denominator = 10.0 if score_type == "ordinal" else 1.0
    full_by_item = full.groupby("item_id", sort=False).score.mean() / denominator
    retained_by_item = retained.groupby("item_id", sort=False).score.mean() / denominator
    common = full_by_item.index.intersection(retained_by_item.index)
    rope = 0.01 if score_type == "ordinal" else 0.02
    if len(common) < 2:
        return {
            "paired_n": int(len(common)), "paired_mean_difference": 0.0,
            "paired_hdi_94": [0.0, 0.0], "rope": rope,
            "equivalence_decision": "undecided", "paired_error": "fewer than two paired items after stopping",
        }
    differences = (full_by_item.loc[common] - retained_by_item.loc[common]).to_numpy(dtype=float)
    mean = float(np.mean(differences))
    standard_deviation = float(np.std(differences, ddof=1))
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
    return {
        "paired_n": int(len(differences)), "paired_mean_difference": mean,
        "paired_hdi_94": [lower, upper], "rope": rope,
        "equivalence_decision": decision, "paired_error": None,
    }


def _aggregate_equivalence(cells: dict[str, dict[str, object]]) -> str:
    """Aggregate registered cell-level uncertainty decisions conservatively."""
    decisions = [str(cell["equivalence_decision"]) for cell in cells.values()]
    if any(decision == "reject" for decision in decisions):
        return "reject"
    if decisions and all(decision == "accept_null" for decision in decisions):
        return "accept_null"
    return "undecided"


def _cell_result(
    path: Path,
    seed: int,
    *,
    parameter_overrides: dict[str, object] | None = None,
    shuffle_items: bool = True,
) -> dict[str, object]:
    from optstop import optimal_stopping_posthoc

    data = pd.read_csv(path)
    score_type = str(data.score_type.iloc[0])
    denominator = 10.0 if score_type == "ordinal" else 1.0
    full_mean = float(data.score.mean() / denominator)
    params = _params(seed)
    params.update(parameter_overrides or {})
    try:
        pruned, summary = optimal_stopping_posthoc(
            data,
            params=params,
            grouping_columns=["regime", "score_type"],
            sample_id_column="item_id",
            epoch_column="epoch",
            score_column="score",
            display_progress=False,
            ordinal_tasks=["ordinal"],
            ordinal_max_score=10,
            continuous_tasks=["continuous"],
            processing_order="epoch_interleaved",
            reanalysis_interval=2,
            max_workers=1,
            shuffle_items=shuffle_items,
            shuffle_seed=seed,
        )
        entry = summary[0] if summary else {"error": "empty optstop summary"}
        retained_mean = float(pruned.score.mean() / denominator) if not pruned.empty else full_mean
        paired = _paired_equivalence(data, pruned, score_type)
        return {
            "efficiency": 1.0 - float(entry.get("percent_items_used") or 1.0),
            "full_mean": full_mean,
            "retained_mean": retained_mean,
            "absolute_difference": abs(full_mean - retained_mean),
            "paired_n": paired["paired_n"],
            "paired_mean_difference": paired["paired_mean_difference"],
            "paired_hdi_94": paired["paired_hdi_94"],
            "rope": paired["rope"],
            "equivalence_decision": paired["equivalence_decision"],
            "error": entry.get("error") or paired["paired_error"],
        }
    except Exception as exc:
        return {
            "efficiency": 0.0,
            "full_mean": full_mean,
            "retained_mean": full_mean,
            "absolute_difference": 0.0,
            "paired_n": 0,
            "paired_mean_difference": 0.0,
            "paired_hdi_94": [0.0, 0.0],
            "rope": 0.01 if score_type == "ordinal" else 0.02,
            "equivalence_decision": "undecided",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _reference(
    data_root: Path,
    seed: int,
    *,
    parameter_overrides: dict[str, object] | None = None,
    shuffle_items: bool = True,
) -> dict[str, object]:
    cells = {
        cell: _cell_result(
            data_root / "cells" / f"{cell}.csv", seed,
            parameter_overrides=parameter_overrides, shuffle_items=shuffle_items,
        )
        for cell in CELLS
    }
    efficiencies = [float(value["efficiency"]) for value in cells.values()]
    return {
        "cells": cells,
        "mean_efficiency": float(np.mean(efficiencies)),
        "mean_absolute_difference": float(np.mean([float(value["absolute_difference"]) for value in cells.values()])),
        "overall_equivalence_decision": _aggregate_equivalence(cells),
    }


def _fixed_budget_reference(data_root: Path) -> dict[str, object]:
    """Evaluate the registered no-stopping baseline.

    A fixed-budget baseline does not run the stopping procedure: it retains
    every planned observation.  Making that computation explicit prevents
    stopped-run efficiency from being incorrectly relabelled as a baseline.
    """
    cells: dict[str, dict[str, object]] = {}
    for cell in CELLS:
        data = pd.read_csv(data_root / "cells" / f"{cell}.csv")
        score_type = str(data.score_type.iloc[0])
        denominator = 10.0 if score_type == "ordinal" else 1.0
        full_mean = float(data.score.mean() / denominator)
        cells[cell] = {
            "efficiency": 0.0,
            "full_mean": full_mean,
            "retained_mean": full_mean,
            "absolute_difference": 0.0,
            "paired_n": int(data.item_id.nunique()),
            "paired_mean_difference": 0.0,
            "paired_hdi_94": [0.0, 0.0],
            "rope": 0.01 if score_type == "ordinal" else 0.02,
            "equivalence_decision": "accept_null",
            "error": None,
        }
    return {
        "cells": cells,
        "mean_efficiency": 0.0,
        "mean_absolute_difference": 0.0,
        "overall_equivalence_decision": "accept_null",
    }


def _copy_dataset(source: Path, destination: Path, variant: str) -> None:
    shutil.copytree(source, destination)
    for path in sorted((destination / "cells").glob("*.csv")):
        data = pd.read_csv(path)
        item_numbers = {item_id: index for index, item_id in enumerate(sorted(data.item_id.astype(str).unique()))}
        item_number = data.item_id.astype(str).map(item_numbers)
        if variant == "row_order":
            data = data.sample(frac=1.0, random_state=17).reset_index(drop=True)
        elif variant == "item_ids":
            data["item_id"] = data.item_id.map(lambda item: "masked-" + hashlib.sha256(str(item).encode()).hexdigest()[:12])
        elif variant == "unequal_observations":
            keep = ~((item_number.isin({0, 3, 6, 9, 12, 15, 18})) & (data.epoch == 4))
            data = data[keep].copy()
        elif variant == "sparse":
            keep = ~((item_number.isin({1, 4, 7, 10, 13, 16, 19})) & (data.epoch >= 3))
            data = data[keep].copy()
        elif variant == "score_scale":
            if str(data.score_type.iloc[0]) == "continuous":
                data["score"] = np.clip(0.08 + 0.84 * data.score.astype(float), 0.0, 1.0)
            elif str(data.score_type.iloc[0]) == "ordinal":
                data["score"] = np.clip(np.rint(data.score.astype(float) * 0.9), 0, 10)
        elif variant == "threshold_stress":
            transformed = 0.5 + 0.55 * (data.score.astype(float) - 0.5)
            if str(data.score_type.iloc[0]) == "ordinal":
                # Ordinal inputs must remain valid categories.  A fractional
                # transformation would accidentally turn this into a different
                # score type rather than a threshold/conservatism stress test.
                data["score"] = np.clip(np.rint(transformed), 0, 10)
            else:
                data["score"] = np.clip(transformed, 0.0, 1.0)
        elif variant == "nonreplication":
            # Raise within-item epoch drift so truncated and full estimates can
            # legitimately diverge. This validates an honest non-replication outcome.
            drift = (data.epoch.astype(float) - data.epoch.astype(float).mean()) * 0.10
            ceiling = 10.0 if str(data.score_type.iloc[0]) == "ordinal" else 1.0
            transformed = np.clip(data.score.astype(float) + drift * ceiling, 0.0, ceiling)
            data["score"] = np.rint(transformed) if ceiling == 10.0 else transformed
        data.to_csv(path, index=False)
    # Hidden inputs must remain manifest-compatible. Recompute file hashes
    # after transformations instead of presenting correct submissions with a
    # manifest that falsely declares its own input files corrupt.
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["files"]:
        entry["sha256"] = _sha256(destination / str(entry["path"]))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def _tolerances(references: list[dict[str, object]]) -> dict[str, object]:
    metrics = ("efficiency", "full_mean", "retained_mean", "absolute_difference", "paired_mean_difference", "paired_hdi_lower", "paired_hdi_upper")

    def metric_value(reference: dict[str, object], cell: str, metric: str) -> float:
        result = reference["cells"][cell]
        if metric == "paired_hdi_lower":
            return float(result["paired_hdi_94"][0])
        if metric == "paired_hdi_upper":
            return float(result["paired_hdi_94"][1])
        return float(result[metric])

    cell_tolerances: dict[str, dict[str, float]] = {}
    for cell in CELLS:
        cell_tolerances[cell] = {
            metric: max(0.01, 3.0 * float(np.std([metric_value(reference, cell, metric) for reference in references], ddof=1)))
            for metric in metrics
        }
    return {
        "cells": cell_tolerances,
        "aggregate": {
            "mean_efficiency": max(0.01, 3.0 * float(np.std([float(reference["mean_efficiency"]) for reference in references], ddof=1))),
            "mean_absolute_difference": max(0.005, 3.0 * float(np.std([float(reference["mean_absolute_difference"]) for reference in references], ddof=1))),
        },
    }


def _differs_from_public(
    public: dict[str, object],
    candidate: dict[str, object],
    tolerances: dict[str, object],
) -> bool:
    """Return whether public hard-coded numerical outputs would be rejected."""
    for cell in CELLS:
        for metric in ("efficiency", "full_mean", "retained_mean", "absolute_difference"):
            if abs(float(public["cells"][cell][metric]) - float(candidate["cells"][cell][metric])) > float(tolerances["cells"][cell][metric]):
                return True
        if int(public["cells"][cell]["paired_n"]) != int(candidate["cells"][cell]["paired_n"]):
            return True
        if abs(float(public["cells"][cell]["paired_mean_difference"]) - float(candidate["cells"][cell]["paired_mean_difference"])) > float(tolerances["cells"][cell]["paired_mean_difference"]):
            return True
        for index, metric in enumerate(("paired_hdi_lower", "paired_hdi_upper")):
            if abs(float(public["cells"][cell]["paired_hdi_94"][index]) - float(candidate["cells"][cell]["paired_hdi_94"][index])) > float(tolerances["cells"][cell][metric]):
                return True
        if public["cells"][cell]["equivalence_decision"] != candidate["cells"][cell]["equivalence_decision"]:
            return True
    for metric in ("mean_efficiency", "mean_absolute_difference"):
        if abs(float(public[metric]) - float(candidate[metric])) > float(tolerances["aggregate"][metric]):
            return True
    return public["overall_equivalence_decision"] != candidate["overall_equivalence_decision"]


def _ablation_reference(data_root: Path, public_runs: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    fixed_budget_runs = [_fixed_budget_reference(data_root) for _ in SEEDS]
    baseline_effects = [
        abs(float(main["mean_efficiency"]) - float(baseline["mean_efficiency"]))
        for main, baseline in zip(public_runs, fixed_budget_runs, strict=True)
    ]
    ordered_runs = [_reference(data_root, seed, shuffle_items=False) for seed in SEEDS]
    conservative_runs = [_reference(data_root, seed, parameter_overrides={"conservatism": 8}) for seed in SEEDS]
    order_effects = [abs(float(main["mean_efficiency"]) - float(alternate["mean_efficiency"])) for main, alternate in zip(public_runs, ordered_runs, strict=True)]
    conservatism_effects = [abs(float(main["mean_efficiency"]) - float(alternate["mean_efficiency"])) for main, alternate in zip(public_runs, conservative_runs, strict=True)]

    def summarize(
        effects: list[float],
        changed_parameter: str,
        *,
        baseline: dict[str, object] | None = None,
    ) -> dict[str, object]:
        effect = float(np.mean(effects))
        uncertainty = float(np.std(effects, ddof=1))
        result: dict[str, object] = {
            "changed_parameter": changed_parameter,
            "effect_size": effect,
            "uncertainty": uncertainty,
            "outcome": "stable" if effect <= 0.02 else "sensitive",
            "tolerance": max(0.01, 3.0 * uncertainty),
            "seed_values": effects,
        }
        if baseline is not None:
            result["baseline"] = baseline
        return result

    return {
        "fixed_budget_baseline": summarize(
            baseline_effects,
            "disable stopping and retain all four epochs",
            baseline={
                "method": "fixed_budget_no_stopping",
                "mean_efficiency": float(fixed_budget_runs[0]["mean_efficiency"]),
                "mean_absolute_difference": float(fixed_budget_runs[0]["mean_absolute_difference"]),
            },
        ),
        "item_order_sensitivity": summarize(order_effects, "disable item shuffling"),
        "stopping_conservatism_sensitivity": summarize(conservatism_effects, "increase conservatism from 5 to 8"),
    }


def _freeze_into(data_root: Path, output: Path) -> None:
    """Write a complete bundle into an empty, private staging directory."""
    manifest = json.loads((data_root / "manifest.json").read_text())
    if manifest["collection"]["items_per_cell"] != 20 or manifest["collection"]["epochs_per_item"] != 4:
        raise ValueError("trace package does not meet the Core Reproduction v1 study contract")
    started = time.perf_counter()
    public_runs = [_reference(data_root, seed) for seed in SEEDS]
    public_errors = {
        cell: sum(run["cells"][cell]["error"] is not None for run in public_runs)
        for cell in CELLS
    }
    if any(public_errors.values()):
        raise RuntimeError(f"public reference has stopping/inference errors: {public_errors}")
    public_reference = public_runs[0]
    tolerances = _tolerances(public_runs)
    ablations = _ablation_reference(data_root, public_runs)
    hidden_root = output / "hidden"
    hidden_root.mkdir()
    variants = []
    for index, name in enumerate(("row_order", "item_ids", "unequal_observations", "sparse", "score_scale", "threshold_stress", "nonreplication")):
        variant_root = hidden_root / name
        _copy_dataset(data_root, variant_root, name)
        variant_runs = [_reference(variant_root, seed) for seed in SEEDS]
        variant_tolerances = _tolerances(variant_runs)
        variants.append({
            "id": name,
            "reference": variant_runs[0],
            "reference_runs": variant_runs,
            "tolerances": variant_tolerances,
        })
    # Reordering and ID changes are still useful robustness cases, but they may
    # legitimately preserve the numerical answer. Do not randomly choose a
    # numerically identical case for the scored hidden run: it would allow a
    # public hard-coded result to earn hidden credit. Every selected case below
    # is empirically checked against the frozen public tolerance.
    scoring_variant_ids = [
        str(variant["id"])
        for variant in variants
        if _differs_from_public(public_reference, variant["reference"], variant["tolerances"])
    ]
    if len(scoring_variant_ids) < 3:
        raise ValueError(
            "fewer than three hidden variants reject public hard-coded results; "
            "collect a study with adequate variation or strengthen the registered variants"
        )
    forecast = {
        "binary": {
            "mean_efficiency_above_50pct": public_reference["mean_efficiency"] > 0.50,
            "any_condition_above_90pct": max(float(cell["efficiency"]) for cell in public_reference["cells"].values()) > 0.90,
            "all_conditions_equivalent": public_reference["overall_equivalence_decision"] == "accept_null",
            "nonreplication_possible": any(item["reference"]["overall_equivalence_decision"] != "accept_null" for item in variants),
        },
        "continuous": {
            "mean_efficiency": public_reference["mean_efficiency"],
            "mean_absolute_difference": public_reference["mean_absolute_difference"],
        },
    }
    bundle = {
        "schema_version": 1,
        "status": "complete",
        "vendor_commit": (VENDOR / "OPTSTOP_COMMIT").read_text().strip(),
        "public_data_manifest_sha256": _sha256(data_root / "manifest.json"),
        "reference_seeds": list(SEEDS),
        "hidden_selection_salt": secrets.token_hex(32),
        "public_reference": public_reference,
        "reference_runs": public_runs,
        "tolerances": tolerances,
        "ablation_reference": ablations,
        "hidden_variants": variants,
        "scoring_hidden_variant_ids": scoring_variant_ids,
        "forecast_outcomes": forecast,
        "judge_evidence": {
            "claim_boundary": "bounded independent reproduction of a current-model study",
            "public_reference": public_reference,
            "ablation_reference": ablations,
            "reference_runtime": {
                "seeds": list(SEEDS),
                "public_reference_errors": public_errors,
            },
            "valid_conclusions": ["replication supported", "evidence insufficient", "claim not supported"],
        },
    }
    (output / "reference_bundle.json").write_text(json.dumps(bundle, indent=2) + "\n")
    (output / "runtime.json").write_text(json.dumps({
        "seeds": list(SEEDS), "tolerances": tolerances,
        "wall_seconds": time.perf_counter() - started,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "reference_errors": public_errors,
    }, indent=2) + "\n")


def freeze(data_root: Path, output: Path) -> None:
    """Atomically publish a frozen bundle or leave no retry-blocking residue."""
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing private bundle: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent))
    try:
        _freeze_into(data_root, staging)
        # ``replace`` is atomic within the same filesystem.  The build
        # preflight can therefore never observe a half-written reference tree.
        staging.replace(output)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=REPO / "verifier" / "private_optstop")
    args = parser.parse_args()
    freeze(args.data, args.output)


if __name__ == "__main__":
    main()
