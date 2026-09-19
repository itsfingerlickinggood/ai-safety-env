# Security model

- Never store `HUD_API_KEY`, provider keys, or `.env` files in this repository.
- The Docker image runs the agent shell as uid/gid 65532 using HUD's `shell_uid` privilege wall and `setpriv --no-new-privs`. This is a defense-in-depth fallback, not equivalent to bubblewrap or user-namespace isolation.
- `/app/verifier` is root-only. The agent shell receives a minimal environment and no API or service secrets.
- `/opt/hud-sandbox/bin/bash` applies seccomp to the shell and descendants, blocking network, process-inspection, mount, namespace, keyring, BPF, and kernel-loading syscalls.
- Hidden evaluation uses a sanitized, link-free, size-bounded workspace copy. The submission runs as uid 65532 under the same syscall policy; hidden test labels stay mode `0600` and verifier-owned. It has a 900-second wall-clock limit, 900 CPU-second limit, 4 GiB address-space limit, 32 MiB output-file limit, and its dedicated process group is killed on timeout.
- The agent workspace has network disabled and is the only filesystem tree mounted into its shell sandbox.
- Reference solutions, analysis files, and local workspaces are excluded from the Docker image.
- Hidden cases are generated outside the agent workspace. Hidden test labels are never bound into the submission sandbox.
- `submission.py` receives read-only calibration/test inputs and a separate writable output directory.
- The optstop Core Reproduction v1 workspace is released in phases: the redacted paper and preregistration schemas are available first; a trusted server-side watcher commits both the forecast and experiment-plan hashes in server memory, stages phase two outside the agent workspace, then atomically publishes `phase_two/` after both files validate.
- Before release, `/app/paper_reproduction/release` and `/app/paper_reproduction/vendor` are root-only alongside the verifier. The agent receives a read-only-copy-derived phase-two workspace only after the watcher validates phase one.
- `verifier/private_optstop/` contains answer-bearing frozen references and hidden matrices. It is Git-ignored, must be present only in a deployment working tree, and is included under root-only `/app/verifier` in the Docker image.
- The grader rejects incomplete, duplicate, non-finite, out-of-range, or threshold-inconsistent predictions.
- Local debug variables `HUD_ALLOW_UNSANDBOXED_GRADER` and `HUD_FORCE_UNSANDBOXED_GRADER` must never be set for production or hosted evaluations.

Before any public benchmark run, run the production sandbox self-test and confirm the trace shell runs as uid 65532, cannot open a network socket, cannot read `/app/verifier`, and can still write the workspace.
