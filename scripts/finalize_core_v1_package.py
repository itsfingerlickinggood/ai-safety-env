"""Package a completed external study and freeze the deployable Core v1 bundle.

This program makes no model calls and does not load credentials.  It is the
single post-collection command: validate score traces, copy only normalized
scores into the release package, atomically freeze private references, and run
the strict repository preflight.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.freeze_optstop_reference import freeze
from scripts.prepare_current_model_study import package


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--collection-metadata", type=Path, required=True)
    parser.add_argument(
        "--output-data", type=Path,
        default=ROOT / "paper_reproduction" / "release" / "data",
    )
    parser.add_argument(
        "--private-reference", type=Path,
        default=ROOT / "verifier" / "private_optstop",
    )
    args = parser.parse_args()

    if not args.input_jsonl.is_file() or not args.collection_metadata.is_file():
        raise SystemExit("completed scored_traces.jsonl and collection_metadata.json are both required")
    metadata = json.loads(args.collection_metadata.read_text())
    estimated_cost = metadata.get("estimated_cost_usd")
    if not isinstance(estimated_cost, (int, float)):
        raise SystemExit("collection metadata has no numeric estimated_cost_usd")
    if args.output_data.exists() or args.private_reference.exists():
        raise SystemExit(
            "refusing to overwrite an existing release data or private reference bundle; "
            "inspect it rather than mixing studies"
        )

    package(args.input_jsonl, args.output_data, args.collection_metadata, float(estimated_cost))
    try:
        freeze(args.output_data, args.private_reference)
    except Exception:
        # Public scores are valid but are not yet a deployable task without a
        # matching reference. Preserve them for diagnosis and do not pretend
        # the package is ready.
        raise
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_optstop_reference.py")],
        cwd=ROOT,
        check=True,
    )
    print(json.dumps({
        "core_v1_package": "ready_for_docker_build",
        "data": str(args.output_data),
        "private_reference": str(args.private_reference),
        "estimated_collection_cost_usd": float(estimated_cost),
    }, indent=2))


if __name__ == "__main__":
    main()
