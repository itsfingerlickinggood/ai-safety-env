"""No-cost integration contract for one-session Core v1 phase release."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import env


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
PLAN = {
    "schema_version": 1,
    "research_question": "Can this fixture exercise a trusted single-session phase release without revealing data early?",
    "hypotheses": ["efficiency", "equivalence", "sensitivity"],
    "data_mapping": ["all fixture cells map to phase-two CSV files"],
    "parameters": {"rope": 0.02},
    "controls": ["seed", "order", "fixed budget"],
    "ablations": ["fixed", "order", "conservatism"],
    "falsification_criteria": ["non-convergence", "large difference"],
    "leakage_controls": ["forecast before release"],
    "analysis_plan": ["run every manifest entry"],
    "analysis_manifest": [
        "low_binary", "mid_binary", "high_binary", "low_ordinal", "mid_ordinal", "high_ordinal",
        "low_continuous", "mid_continuous", "high_continuous", "fixed_budget_baseline",
        "item_order_sensitivity", "stopping_conservatism_sensitivity",
    ],
}


async def main() -> None:
    old_root, old_release, old_vendor = env.OPT_ROOT, env.OPT_RELEASE, env.OPT_VENDOR
    old_released, old_hash, old_plan_hash = env._phase_released, env._locked_forecast_hash, env._locked_plan_hash
    try:
        with tempfile.TemporaryDirectory(prefix="optstop-phase-release-") as raw:
            root = Path(raw)
            workspace = root / "workspace"
            release = root / "release"
            vendor = root / "vendor-source"
            workspace.mkdir()
            (workspace / "task.md").write_text("fixture phase-one prompt\n")
            (release / "data" / "cells").mkdir(parents=True)
            (release / "data" / "manifest.json").write_text("{}")
            (release / "data" / "cells" / "low_binary.csv").write_text("fixture\n")
            (release / "analysis_manifest.json").write_text("{}")
            vendor.mkdir()
            (vendor / "__init__.py").write_text("fixture = True\n")
            env.OPT_ROOT, env.OPT_RELEASE, env.OPT_VENDOR = workspace, release, vendor
            env._phase_released, env._locked_forecast_hash, env._locked_plan_hash = False, None, None
            # The HUD server supports exactly one prompt and one final grade.
            # Before release, the template must return a normal zero-score
            # EvaluationResult on that grade rather than trying to yield a
            # second conversational prompt.
            generator = env.reproduce_optstop_core.func()
            assert await generator.__anext__() == "fixture phase-one prompt\n"
            incomplete = await generator.asend("finished too early")
            assert incomplete.reward == 0.0
            await generator.aclose()
            (workspace / "forecast.json").write_text(json.dumps(FORECAST))
            (workspace / "experiment_plan.json").write_text(json.dumps(PLAN))
            watcher = asyncio.create_task(env._watch_for_phase_two())
            await asyncio.wait_for(watcher, timeout=2)
            assert env._phase_released
            assert env._locked_forecast_hash == hashlib.sha256((workspace / "forecast.json").read_bytes()).hexdigest()
            assert env._locked_plan_hash == hashlib.sha256((workspace / "experiment_plan.json").read_bytes()).hexdigest()
            assert (workspace / "PHASE_TWO_READY").is_file()
            assert (workspace / "phase_two" / "data" / "cells" / "low_binary.csv").read_text() == "fixture\n"
            assert (workspace / "phase_two" / "vendor" / "__init__.py").is_file()

            # A pre-created phase-two destination must stop the root-side
            # release rather than permit a symlink or overwrite attack.
            second = root / "second-workspace"
            second.mkdir()
            (second / "phase_two").mkdir()
            env.OPT_ROOT = second
            try:
                env._release_optstop_phase_two()
            except RuntimeError as exc:
                assert "already exists" in str(exc)
            else:
                raise AssertionError("pre-created phase-two destination unexpectedly released")

            # A source-side failure after copying the release data into the
            # private staging directory must expose nothing. The watcher has
            # already committed both hashes, so retrying cannot permit a
            # revised preregistration after seeing experimental inputs.
            failed = root / "failed-workspace"
            failed.mkdir()
            (failed / "forecast.json").write_text(json.dumps(FORECAST))
            (failed / "experiment_plan.json").write_text(json.dumps(PLAN))
            env.OPT_ROOT, env.OPT_VENDOR = failed, root / "missing-vendor"
            env._phase_released, env._locked_forecast_hash, env._locked_plan_hash = False, None, None
            failed_watcher = asyncio.create_task(env._watch_for_phase_two())
            await asyncio.sleep(0.05)
            failed_watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await failed_watcher
            assert not (failed / "phase_two").exists()
            assert env._locked_forecast_hash == hashlib.sha256((failed / "forecast.json").read_bytes()).hexdigest()
            assert env._locked_plan_hash == hashlib.sha256((failed / "experiment_plan.json").read_bytes()).hexdigest()
    finally:
        env.OPT_ROOT, env.OPT_RELEASE, env.OPT_VENDOR = old_root, old_release, old_vendor
        env._phase_released, env._locked_forecast_hash, env._locked_plan_hash = old_released, old_hash, old_plan_hash
    print('{"phase_release_watcher": "passed", "single_grade_before_release": true, "release_after_valid_phase_one": true, "precreated_destination_rejected": true}')


if __name__ == "__main__":
    asyncio.run(main())
