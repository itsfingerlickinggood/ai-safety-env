"""No-cost end-to-end Core v1 template, release, and deterministic-grade probe."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import env
import verifier.optstop_score as scorer
from verifier.output_validation import ABLATIONS, CELLS


FORECAST = {
    "schema_version": 1,
    "binary": [
        {"id": "mean_efficiency_above_50pct", "probability": 0.0},
        {"id": "any_condition_above_90pct", "probability": 0.0},
        {"id": "all_conditions_equivalent", "probability": 1.0},
        {"id": "nonreplication_possible", "probability": 0.0},
    ],
    "continuous": [
        {"id": "mean_efficiency", "mean": 0.4, "std": 0.1},
        {"id": "mean_absolute_difference", "mean": 0.0, "std": 0.1},
    ],
}
PLAN = {
    "schema_version": 1,
    "research_question": "Can a controlled fixture validate the trusted one-session Core v1 release and grade lifecycle?",
    "hypotheses": ["efficiency", "equivalence", "sensitivity"],
    "data_mapping": ["map each registered cell to its score trace"],
    "parameters": {"rope": 0.02, "seed": 42},
    "controls": ["seed", "order", "fixed budget"],
    "ablations": ["fixed", "order", "conservatism"],
    "falsification_criteria": ["non-convergence", "large difference"],
    "leakage_controls": ["forecast before release"],
    "analysis_plan": ["run every registered cell"],
    "analysis_manifest": sorted(CELLS | ABLATIONS),
}


def cell() -> dict[str, object]:
    return {
        "efficiency": 0.4, "full_mean": 0.5, "retained_mean": 0.5,
        "absolute_difference": 0.0, "paired_n": 20,
        "paired_mean_difference": 0.0, "paired_hdi_94": [-0.01, 0.01],
        "rope": 0.02, "equivalence_decision": "accept_null", "error": None,
    }


def results() -> dict[str, object]:
    return {
        "schema_version": 1, "cells": {identifier: cell() for identifier in CELLS},
        "mean_efficiency": 0.4, "mean_absolute_difference": 0.0,
        "overall_equivalence_decision": "accept_null",
    }


def ablations() -> dict[str, object]:
    return {
        "schema_version": 1,
        "ablations": [
            {"id": identifier, "changed_parameter": "registered change", "effect_size": 0.1,
             "uncertainty": 0.01, "outcome": "sensitive", "interpretation": "Fixture interpretation."}
            for identifier in sorted(ABLATIONS)
        ],
    }


def tolerances() -> dict[str, object]:
    return {
        "cells": {
            identifier: {
                metric: 0.01 for metric in (
                    "efficiency", "full_mean", "retained_mean", "absolute_difference",
                    "paired_mean_difference", "paired_hdi_lower", "paired_hdi_upper",
                )
            }
            for identifier in CELLS
        },
        "aggregate": {"mean_efficiency": 0.01, "mean_absolute_difference": 0.01},
    }


def generic_submission() -> str:
    payload = json.dumps(results())
    return f'''import argparse, json\nfrom pathlib import Path\np=argparse.ArgumentParser(); p.add_argument("--input-dir", type=Path); p.add_argument("--output", type=Path); a=p.parse_args()\nassert (a.input_dir / "manifest.json").is_file()\na.output.write_text({payload!r})\n'''


async def main() -> None:
    old = (env.OPT_ROOT, env.OPT_RELEASE, env.OPT_VENDOR, env._phase_released, env._locked_forecast_hash, env._locked_plan_hash, scorer.PRIVATE)
    old_skip = os.environ.get("HUD_SKIP_LLM_JUDGE")
    try:
        with tempfile.TemporaryDirectory(prefix="optstop-full-task-") as raw:
            root = Path(raw)
            workspace, release, vendor, private = root / "workspace", root / "release", root / "vendor", root / "private"
            workspace.mkdir()
            (workspace / "task.md").write_text("fixture task\n")
            (release / "data" / "cells").mkdir(parents=True)
            (release / "data" / "manifest.json").write_text("{}")
            (release / "data" / "cells" / "low_binary.csv").write_text("fixture\n")
            (release / "analysis_manifest.json").write_text("{}")
            vendor.mkdir()
            (vendor / "__init__.py").write_text("fixture = True\n")
            hidden = private / "hidden" / "fixture"
            (hidden / "cells").mkdir(parents=True)
            (hidden / "manifest.json").write_text("{}")
            for identifier in CELLS:
                (hidden / "cells" / f"{identifier}.csv").write_text("fixture\n")
            reference = results()
            bundle = {
                "schema_version": 1, "status": "complete", "hidden_selection_salt": "0" * 64,
                "public_reference": {"cells": reference["cells"], "mean_efficiency": 0.4, "mean_absolute_difference": 0.0, "overall_equivalence_decision": "accept_null"},
                "tolerances": tolerances(), "ablation_reference": {
                    identifier: {"changed_parameter": "registered change", "effect_size": 0.1, "uncertainty": 0.01, "outcome": "sensitive", "tolerance": 0.01}
                    for identifier in ABLATIONS
                },
                "hidden_variants": [{"id": "fixture", "reference": {"cells": reference["cells"]}, "tolerances": tolerances()}],
                "scoring_hidden_variant_ids": ["fixture"],
                "forecast_outcomes": {"binary": {"mean_efficiency_above_50pct": False, "any_condition_above_90pct": False, "all_conditions_equivalent": True, "nonreplication_possible": False}, "continuous": {"mean_efficiency": 0.4, "mean_absolute_difference": 0.0}},
                "judge_evidence": {"claim_boundary": "fixture", "public_reference": reference, "valid_conclusions": ["replication supported"]},
            }
            (private / "reference_bundle.json").write_text(json.dumps(bundle))
            env.OPT_ROOT, env.OPT_RELEASE, env.OPT_VENDOR = workspace, release, vendor
            env._phase_released, env._locked_forecast_hash, env._locked_plan_hash = False, None, None
            scorer.PRIVATE = private
            os.environ["HUD_SKIP_LLM_JUDGE"] = "1"

            generator = env.reproduce_optstop_core.func()
            assert await generator.__anext__() == "fixture task\n"
            (workspace / "forecast.json").write_text(json.dumps(FORECAST))
            (workspace / "experiment_plan.json").write_text(json.dumps(PLAN))
            watcher = asyncio.create_task(env._watch_for_phase_two())
            await asyncio.wait_for(watcher, timeout=2)
            (workspace / "reproduction_results.json").write_text(json.dumps(results()))
            (workspace / "ablations.json").write_text(json.dumps(ablations()))
            (workspace / "submission.py").write_text(generic_submission())
            (workspace / "final_report.md").write_text("Methods\nResults\nAblations\nUncertainty\nLimitations\n" + "Fixture report evidence. " * 40)
            graded = await generator.asend("fixture complete")
            assert graded.reward >= 0.89, graded
            assert graded.info["notes"] == ["fixture"], graded.info
            await generator.aclose()
    finally:
        env.OPT_ROOT, env.OPT_RELEASE, env.OPT_VENDOR, env._phase_released, env._locked_forecast_hash, env._locked_plan_hash, scorer.PRIVATE = old
        if old_skip is None:
            os.environ.pop("HUD_SKIP_LLM_JUDGE", None)
        else:
            os.environ["HUD_SKIP_LLM_JUDGE"] = old_skip
    print('{"optstop_full_task": "passed", "phase_release": true, "single_template_grade": true, "deterministic_reward": true}')


if __name__ == "__main__":
    asyncio.run(main())
