from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from hud import Task
from hud.clients import connect
from hud.eval import LocalRuntime


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HUD_ALLOW_UNSANDBOXED_GRADER", "1")
os.environ.setdefault("HUD_FORCE_UNSANDBOXED_GRADER", "1")


async def main() -> None:
    task = Task(
        env="ai-safety-monitoring-regression",
        id="research-sabotage-monitoring",
        args={},
        slug="long-horizon-sabotage-research-001",
    )
    async with LocalRuntime(ROOT / "env_monitoring.py")(task) as runtime:
        async with connect(runtime) as client:
            bindings = [
                {
                    "name": binding.name,
                    "protocol": binding.protocol,
                    "isolation": binding.params.get("isolation"),
                    "cwd": binding.params.get("cwd"),
                }
                for binding in client.manifest.bindings
            ]
            started = await client.start_task(task.id, task.args)
            shell = await client.open("shell")
            leak_probe = await shell.run(
                "if test -r ../verifier/score.py; "
                "then echo accessible; else echo blocked; fi",
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "reference" / "solve_reference.py"),
                    "--workspace",
                    str(ROOT / "workspace"),
                ],
                check=True,
            )
            graded = await client.grade({"answer": "Reference lifecycle probe completed."})
    print(
        json.dumps(
            {
                "bindings": bindings,
                "hidden_labels_from_agent_shell": leak_probe.stdout.strip(),
                "prompt": started,
                "graded": graded,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
