# Security model

- Never store `HUD_API_KEY`, provider keys, or `.env` files in this repository.
- The Docker image runs the agent shell as uid/gid 65532 using HUD's `shell_uid` privilege wall and `setpriv --no-new-privs`.
- `/app/verifier` is root-only. The agent shell receives a minimal environment and no API or service secrets.
- `/opt/hud-sandbox/bin/bash` applies seccomp to the shell and descendants, blocking network, process-inspection, mount, namespace, keyring, BPF, and kernel-loading syscalls.
- Hidden evaluation uses a sanitized, link-free, size-bounded workspace copy. The submission runs as uid 65532 under the same syscall policy; hidden test labels stay mode `0600` and verifier-owned.
- The agent workspace has network disabled and is the only filesystem tree mounted into its shell sandbox.
- Reference solutions, analysis files, and local workspaces are excluded from the Docker image.
- Hidden cases are generated outside the agent workspace. Hidden test labels are never bound into the submission sandbox.
- `submission.py` receives read-only calibration/test inputs and a separate writable output directory.
- The grader rejects incomplete, duplicate, non-finite, out-of-range, or threshold-inconsistent predictions.
- Local debug variables `HUD_ALLOW_UNSANDBOXED_GRADER` and `HUD_FORCE_UNSANDBOXED_GRADER` must never be set for production or hosted evaluations.

Before any public benchmark run, run the production sandbox self-test and confirm the trace shell runs as uid 65532, cannot open a network socket, cannot read `/app/verifier`, and can still write the workspace.
