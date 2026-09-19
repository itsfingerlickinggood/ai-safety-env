"""Isolated HUD environment for the retained sabotage-monitoring regression."""

from __future__ import annotations

import os
import shutil
import signal
from pathlib import Path

from hud.environment import Environment
from hud.graders import EvaluationResult, SubScore

from verifier import score_workspace
from verifier.cases import materialize_public_dataset


ROOT = Path("workspace")
SEED = Path("workspace_seed")
AGENT_UID = int(os.environ.get("HUD_AGENT_UID", "65532"))
AGENT_GID = int(os.environ.get("HUD_AGENT_GID", str(AGENT_UID)))

env = Environment(name="ai-safety-monitoring-regression")
env.workspace(
    ROOT,
    network=False,
    track_files=True,
    shell_uid=AGENT_UID,
    shell_gid=AGENT_GID,
    env={"PATH": "/opt/hud-sandbox/bin:/usr/local/bin:/usr/bin:/bin"},
    require_isolation=False,
)


def _hand_workspace_to_agent(root: Path) -> None:
    if os.geteuid() != 0:
        return
    for path in [root, *root.rglob("*")]:
        if not path.is_symlink():
            os.chown(path, AGENT_UID, AGENT_GID)


def _kill_agent_processes() -> None:
    proc = Path("/proc")
    if not proc.is_dir():
        return
    for _ in range(3):
        found = False
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                uid_line = next(line for line in (entry / "status").read_text().splitlines() if line.startswith("Uid:"))
                if int(uid_line.split()[1]) == AGENT_UID:
                    os.kill(int(entry.name), signal.SIGKILL)
                    found = True
            except (FileNotFoundError, ProcessLookupError, PermissionError, StopIteration):
                continue
        if not found:
            break


@env.initialize
async def _seed_workspace() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for child in ROOT.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    shutil.copytree(SEED, ROOT, dirs_exist_ok=True)
    materialize_public_dataset(ROOT)
    _hand_workspace_to_agent(ROOT)


@env.template(
    id="research-sabotage-monitoring",
    description=(
        "Forecast, reproduce, critique, and extend a redacted AI-safety sabotage-monitoring "
        "study through executable artifact audits and independent hidden attack families."
    ),
)
async def reproduce_monitoring_paper() -> object:
    answer = yield (ROOT / "task.md").read_text()
    _kill_agent_processes()
    scored = score_workspace(ROOT)
    subscores = [
        SubScore(name=name, value=float(value), weight=float(scored["weights"].get(name, 0.0)))
        for name, value in scored["components"].items()
        if name in scored["weights"]
    ]
    yield EvaluationResult(
        reward=float(scored["reward"]),
        subscores=subscores,
        info={
            "hidden_metrics": scored["hidden_metrics"],
            "hidden_baseline_metrics": scored["hidden_baseline_metrics"],
            "hidden_family_recall": scored["hidden_family_recall"],
            "notes": scored["notes"],
            "agent_final_answer": answer,
        },
        content="Long-horizon research score with executable reproduction and hidden family holdouts.",
    )
