from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verifier.score import score_workspace  # noqa: E402
from verifier.cases import materialize_public_dataset  # noqa: E402

workspace = ROOT / ".reference_workspace"
shutil.rmtree(workspace, ignore_errors=True)
shutil.copytree(ROOT / "workspace_seed", workspace)
materialize_public_dataset(workspace)

# The shipped reference solver is deterministic and uses only public material.
subprocess.run(
    [sys.executable, str(ROOT / "reference" / "solve_reference.py"), "--workspace", str(workspace)],
    check=True,
)

# macOS validation deliberately opts into the unsandboxed fallback. Production
# uses the image's low-privilege seccomp launcher instead.
os.environ.setdefault("HUD_ALLOW_UNSANDBOXED_GRADER", "1")
os.environ.setdefault("HUD_FORCE_UNSANDBOXED_GRADER", "1")
result = score_workspace(workspace)
print(json.dumps(result, indent=2))

if result["reward"] < 0.99:
    raise SystemExit(f"reference reward unexpectedly low: {result['reward']}")
