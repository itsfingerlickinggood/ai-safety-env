from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path


UID = 65532
GID = 65532

PROBE = r'''
import json
import os
import socket
from pathlib import Path

result = {"uid": os.getuid(), "gid": os.getgid()}
try:
    socket.socket()
    result["network_blocked"] = False
except PermissionError:
    result["network_blocked"] = True
try:
    for verifier in ("score.py", "optstop_score.py"):
        Path("/app/verifier", verifier).read_text()
    result["verifier_hidden"] = False
except PermissionError:
    result["verifier_hidden"] = True
try:
    for release_path in (
        Path("/app/paper_reproduction/release/analysis_manifest.json"),
        Path("/app/paper_reproduction/vendor/optstop/__init__.py"),
    ):
        release_path.read_text()
    result["phase_two_hidden"] = False
except PermissionError:
    result["phase_two_hidden"] = True
Path("write-ok.txt").write_text("ok\n")
result["workspace_writable"] = Path("write-ok.txt").read_text() == "ok\n"
result["hud_key_hidden"] = "HUD_API_KEY" not in os.environ
print(json.dumps(result))
'''


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hud-sandbox-selftest-") as raw:
        work = Path(raw)
        os.chown(work, UID, GID)
        command = [
            "/usr/bin/setpriv",
            "--reuid",
            str(UID),
            "--regid",
            str(GID),
            "--clear-groups",
            "--no-new-privs",
            "--",
            "/usr/bin/env",
            "-i",
            "PATH=/opt/hud-sandbox/bin:/usr/local/bin:/usr/bin:/bin",
            f"HOME={work}",
            "/opt/hud-sandbox/bin/bash",
            "-lc",
            f"cd {work} && /usr/local/bin/python -c {shlex.quote(PROBE)}",
        ]
        expected = {
            "uid": UID,
            "gid": GID,
            "network_blocked": True,
            "verifier_hidden": True,
            "phase_two_hidden": True,
            "workspace_writable": True,
            "hud_key_hidden": True,
        }
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            raise SystemExit(f"agent-shell sandbox self-test failed: {proc.stderr}")
        shell_result = json.loads(proc.stdout)
        if shell_result != expected:
            raise SystemExit(f"agent-shell sandbox mismatch: {shell_result!r}")

        (work / "write-ok.txt").unlink()
        grader_command = [
            "/usr/local/bin/hud-sandbox-exec",
            "--uid",
            str(UID),
            "--gid",
            str(GID),
            "/usr/local/bin/python",
            "-c",
            PROBE,
        ]
        grader = subprocess.run(
            grader_command,
            cwd=work,
            capture_output=True,
            text=True,
            check=False,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HUD_API_KEY": "must-not-leak"},
        )
        if grader.returncode != 0:
            raise SystemExit(f"grader sandbox self-test failed: {grader.stderr}")
        grader_result = json.loads(grader.stdout)
        if grader_result != expected:
            raise SystemExit(f"grader sandbox mismatch: {grader_result!r}")
        print(
            json.dumps(
                {"production_sandbox": "passed", "agent_shell": shell_result, "grader": grader_result},
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
