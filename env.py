from __future__ import annotations

import asyncio
import contextlib
import shutil
import os
import hashlib
import json
import tempfile
from pathlib import Path

from hud.environment import Environment
from hud.graders import EvaluationResult, LLMJudgeGrader, SubScore

OPT_ROOT = Path("optstop_workspace")
OPT_PHASE_ONE = Path("paper_reproduction/phase1")
OPT_RELEASE = Path("paper_reproduction/release")
OPT_VENDOR = Path("paper_reproduction/vendor")
CORE_ANALYSIS_IDS = {
    "low_binary", "mid_binary", "high_binary",
    "low_ordinal", "mid_ordinal", "high_ordinal",
    "low_continuous", "mid_continuous", "high_continuous",
    "fixed_budget_baseline", "item_order_sensitivity", "stopping_conservatism_sensitivity",
}
AGENT_UID = int(os.environ.get("HUD_AGENT_UID", "65532"))
AGENT_GID = int(os.environ.get("HUD_AGENT_GID", str(AGENT_UID)))
FORECAST_TAMPER_REWARD_CAP = 0.50
PHASE_POLL_SECONDS = 0.25
_phase_watcher: asyncio.Task[None] | None = None
_phase_released = False
_locked_forecast_hash: str | None = None
_locked_plan_hash: str | None = None

from verifier.optstop_score import score_optstop_workspace
from verifier.output_validation import valid_forecast, valid_plan

# This environment exposes only the paper task workspace.  The retained
# monitoring regression is deployed from env_monitoring.py.
env = Environment(name="optstop-core-reproduction-v1")
env.workspace(
    OPT_ROOT,
    network=False,
    track_files=True,
    shell_uid=AGENT_UID,
    shell_gid=AGENT_GID,
    env={"PATH": "/opt/hud-sandbox/bin:/usr/local/bin:/usr/bin:/bin"},
    require_isolation=False,
)


def _hand_workspace_to_agent(root: Path) -> None:
    """Make only the workspace writable by the unprivileged agent uid."""
    if os.geteuid() != 0:
        # Local macOS lifecycle probes do not have permission to emulate the
        # production numeric UID. They retain the invoking user's ownership.
        return
    for path in [root, *root.rglob("*")]:
        if path.is_symlink():
            continue
        os.chown(path, AGENT_UID, AGENT_GID)


def _hand_tree_to_agent(root: Path) -> None:
    """Hand only a newly copied phase-two tree to the shell UID."""
    if os.geteuid() != 0:
        return
    for path in [root, *root.rglob("*")]:
        if not path.is_symlink():
            os.chown(path, AGENT_UID, AGENT_GID)


@env.initialize
async def _seed_workspace() -> None:
    """Each HUD rollout gets a fresh environment; seed the research workspace once."""
    OPT_ROOT.mkdir(parents=True, exist_ok=True)
    for child in OPT_ROOT.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    shutil.copytree(OPT_PHASE_ONE, OPT_ROOT, dirs_exist_ok=True)
    _hand_workspace_to_agent(OPT_ROOT)
    global _phase_watcher, _phase_released, _locked_forecast_hash, _locked_plan_hash
    _phase_released = False
    _locked_forecast_hash = None
    _locked_plan_hash = None
    if _phase_watcher is not None:
        _phase_watcher.cancel()
    _phase_watcher = asyncio.create_task(_watch_for_phase_two())


def _valid_phase_one_forecast(path: Path) -> bool:
    try:
        return valid_forecast(json.loads(path.read_text()))
    except Exception:
        return False


def _valid_phase_one_plan(path: Path) -> bool:
    try:
        return valid_plan(json.loads(path.read_text()))
    except Exception:
        return False


def _release_optstop_phase_two() -> None:
    """Atomically release staged inputs after preregistration is committed."""
    data = OPT_RELEASE / "data"
    manifest = data / "manifest.json"
    if not manifest.is_file() or not any(data.glob("cells/*.csv")):
        raise RuntimeError(
            "optstop Core Reproduction v1 is not ready: generate and validate the non-synthetic trace package before deployment"
        )
    destination = OPT_ROOT / "phase_two"
    # An agent may create a file or a nonempty directory here, but cannot
    # replace OPT_ROOT itself because its parent is server-owned. Refuse a
    # conflicting directory; a link or file is atomically replaced below.
    if destination.is_dir() and not destination.is_symlink():
        raise RuntimeError("phase-two release target already exists")
    staging_root = Path(tempfile.mkdtemp(prefix=".optstop-phase-two-", dir=OPT_ROOT.parent))
    staged = staging_root / "phase_two"
    try:
        shutil.copytree(OPT_RELEASE, staged)
        shutil.copytree(OPT_VENDOR, staged / "vendor")
        # The whole release becomes visible through one directory rename only
        # after every source copy has completed successfully.
        os.replace(staged, destination)
        _hand_tree_to_agent(destination)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)


async def _watch_for_phase_two() -> None:
    """Release phase two inside the one-prompt/one-grade HUD lifecycle.

    HUD's template protocol does not support a second conversational yield.
    This trusted server-side watcher observes the agent-owned phase-one files,
    stores the lock hash in process memory, and copies the root-owned release
    package only after both strict schemas validate.
    """
    global _phase_released, _locked_forecast_hash, _locked_plan_hash
    forecast_path = OPT_ROOT / "forecast.json"
    plan_path = OPT_ROOT / "experiment_plan.json"
    while not _phase_released:
        if forecast_path.is_file() and plan_path.is_file() and _valid_phase_one_forecast(forecast_path) and _valid_phase_one_plan(plan_path):
            forecast_lock = hashlib.sha256(forecast_path.read_bytes()).hexdigest()
            plan_lock = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            if _locked_forecast_hash is None and _locked_plan_hash is None:
                # Commit both phase-one artifacts before even staging data.
                _locked_forecast_hash = forecast_lock
                _locked_plan_hash = plan_lock
            if forecast_lock != _locked_forecast_hash or plan_lock != _locked_plan_hash:
                await asyncio.sleep(PHASE_POLL_SECONDS)
                continue
            try:
                _release_optstop_phase_two()
            except Exception:
                # A malformed or intentionally pre-created destination is a
                # fail-closed task error, not a reason to reveal phase-two data.
                await asyncio.sleep(PHASE_POLL_SECONDS)
                continue
            _phase_released = True
            # This notice is informational only. The authoritative hash lives
            # in server memory so the agent cannot forge it by replacing files.
            (OPT_ROOT / "PHASE_TWO_READY").write_text("phase two released; do not alter forecast.json\n")
        await asyncio.sleep(PHASE_POLL_SECONDS)


@env.shutdown
async def _stop_phase_watcher() -> None:
    global _phase_watcher
    if _phase_watcher is not None:
        _phase_watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _phase_watcher
        _phase_watcher = None


def _apply_reward_caps(reward: float, scored: dict[str, object], *, forecast_locked: bool, plan_locked: bool) -> float:
    """Apply integrity caps after all component scores have been calculated."""
    if not forecast_locked:
        scored["notes"].append("reward capped because forecast.json changed after phase one")
        return min(reward, FORECAST_TAMPER_REWARD_CAP)
    if not plan_locked:
        scored["notes"].append("reward capped because experiment_plan.json changed after phase one")
        return min(reward, FORECAST_TAMPER_REWARD_CAP)
    return reward


@env.template(
    id="optstop-core-reproduction-v1",
    description="Forecast and independently reproduce the measured central 3x3 study from a redacted optimal-stopping paper.",
)
async def reproduce_optstop_core() -> object:
    prompt = (OPT_ROOT / "task.md").read_text()
    answer = yield prompt
    forecast_path = OPT_ROOT / "forecast.json"
    plan_path = OPT_ROOT / "experiment_plan.json"
    if not _phase_released or _locked_forecast_hash is None or _locked_plan_hash is None:
        yield EvaluationResult(
            reward=0.0,
            info={"notes": ["phase two was never released: submit valid phase-one artifacts and wait for PHASE_TWO_READY before ending the task"], "agent_final_answer": answer},
            content="Core reproduction did not reach the trusted phase-two release.",
        )
        return
    current_hash = hashlib.sha256(forecast_path.read_bytes()).hexdigest() if forecast_path.exists() else ""
    current_plan_hash = hashlib.sha256(plan_path.read_bytes()).hexdigest() if plan_path.exists() else ""
    forecast_locked = bool(_locked_forecast_hash and _locked_forecast_hash == current_hash)
    plan_locked = bool(_locked_plan_hash and _locked_plan_hash == current_plan_hash)
    scored = score_optstop_workspace(OPT_ROOT, forecast_locked=forecast_locked, plan_locked=plan_locked)
    deterministic_ready = (
        scored["components"]["numerical_reproduction"] >= 0.5
        and scored["components"]["ablations"] >= 0.5
        and bool(scored["report_context"])
    )
    if not deterministic_ready:
        judge_value = 0.0
        scored["notes"].append("LLM report judge skipped because deterministic prerequisites are incomplete")
    elif os.environ.get("HUD_SKIP_LLM_JUDGE") == "1":
        judge_value = 0.0
    else:
        try:
            judge = await LLMJudgeGrader.compute_score(
                answer=scored["report_context"],
                question=(
                    "Judge only the scientific interpretation in the report bundle. The golden evidence is authoritative. "
                    "Require accurate claims, explicit uncertainty, an honest replication/non-replication conclusion, and no invented evidence."
                ),
                model="claude-sonnet-4-6",
                criteria=[
                    "The report's conclusion matches the supplied golden evidence and does not overclaim replication.",
                    "The report explains uncertainty, convergence or failure handling, and limitations accurately.",
                    "The report distinguishes evidence supporting a claim, insufficient evidence, and evidence not supporting a claim.",
                ],
            )
            judge_value = float(judge.value)
        except Exception as exc:
            raise RuntimeError(f"LLM report judge unavailable; mark this rollout invalid and retry: {exc}") from exc
    scored["components"]["report_interpretation"] = judge_value
    reward = sum(float(scored["weights"][name]) * float(value) for name, value in scored["components"].items())
    if scored["components"]["numerical_reproduction"] < 0.5 or scored["components"]["ablations"] < 0.5:
        reward = min(reward, 0.50)
    reward = _apply_reward_caps(reward, scored, forecast_locked=forecast_locked, plan_locked=plan_locked)
    subscores = [SubScore(name=k, value=float(v), weight=float(scored["weights"][k])) for k, v in scored["components"].items()]
    yield EvaluationResult(
        reward=float(reward),
        subscores=subscores,
        info={"notes": scored["notes"], "agent_final_answer": answer},
        content="Bounded independent optstop Core Reproduction v1 score.",
    )
