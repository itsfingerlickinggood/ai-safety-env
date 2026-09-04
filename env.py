from __future__ import annotations

import shutil
import os
import signal
from pathlib import Path

from hud.environment import Environment
from hud.graders import EvaluationResult, SubScore

ROOT = Path("workspace")
SEED = Path("workspace_seed")
AGENT_UID = int(os.environ.get("HUD_AGENT_UID", "65532"))
AGENT_GID = int(os.environ.get("HUD_AGENT_GID", str(AGENT_UID)))

from verifier import score_workspace
from verifier.cases import materialize_public_dataset

# HUD v6 environment. The workspace becomes an SSH-backed shell/files capability.
env = Environment(name="long-horizon-safety-research")
env.workspace(
    ROOT,
    network=False,
    track_files=True,
    # HUD's hosted builder does not permit user namespaces, so bubblewrap is
    # not a portable production boundary.  A numeric uid plus setpriv is HUD's
    # supported fallback privilege wall.  The image's bash wrapper adds a
    # seccomp policy to every agent shell and all of its descendants.
    shell_uid=AGENT_UID,
    shell_gid=AGENT_GID,
    env={"PATH": "/opt/hud-sandbox/bin:/usr/local/bin:/usr/bin:/bin"},
    require_isolation=False,
)


def _hand_workspace_to_agent() -> None:
    """Make only the workspace writable by the unprivileged agent uid."""
    for path in [ROOT, *ROOT.rglob("*")]:
        if path.is_symlink():
            continue
        os.chown(path, AGENT_UID, AGENT_GID)


def _kill_agent_processes() -> None:
    """Stop agent-owned background jobs before the root verifier reads files."""
    proc = Path("/proc")
    if not proc.is_dir():
        return
    for _ in range(3):
        found = False
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                status = (entry / "status").read_text()
                uid_line = next(line for line in status.splitlines() if line.startswith("Uid:"))
                real_uid = int(uid_line.split()[1])
                if real_uid == AGENT_UID:
                    os.kill(int(entry.name), signal.SIGKILL)
                    found = True
            except (FileNotFoundError, ProcessLookupError, PermissionError, StopIteration):
                continue
        if not found:
            break


@env.initialize
async def _seed_workspace() -> None:
    """Each HUD rollout gets a fresh environment; seed the research workspace once."""
    for child in ROOT.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)
    shutil.copytree(SEED, ROOT, dirs_exist_ok=True)
    materialize_public_dataset(ROOT)
    _hand_workspace_to_agent()


@env.template(
    id="research-sabotage-monitoring",
    description=(
        "Forecast, reproduce, critique, and extend a redacted AI-safety sabotage-monitoring "
        "study through executable artifact audits and independent hidden attack families."
    ),
)
async def reproduce_monitoring_paper() -> object:
    prompt = (ROOT / "task.md").read_text()
    answer = yield prompt

    _kill_agent_processes()
    scored = score_workspace(ROOT)
    subscores = [
        SubScore(
            name=name,
            value=float(value),
            weight=float(scored["weights"].get(name, 0.0)),
        )
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
