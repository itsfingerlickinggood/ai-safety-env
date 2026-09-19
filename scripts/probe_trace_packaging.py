"""No-cost end-to-end contract test for trace normalization and packaging."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.prepare_current_model_study import CELLS, EPOCHS_PER_ITEM, ITEMS_PER_CELL, package


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="optstop-trace-package-") as raw:
        root = Path(raw)
        traces = root / "traces.jsonl"
        metadata = root / "metadata.json"
        output = root / "data"
        rows = []
        for cell in CELLS:
            regime, score_type = cell.split("_", 1)
            for item in range(ITEMS_PER_CELL):
                for epoch in range(1, EPOCHS_PER_ITEM + 1):
                    rows.append({
                        "cell_id": cell, "regime": regime, "score_type": score_type,
                        "item_id": f"test-{item}", "epoch": epoch,
                        "score": item % 11 if score_type == "ordinal" else (item % 10) / 10,
                        "model_id": "claude-sonnet-4-6", "input_sha256": hashlib.sha256(f"{cell}-{item}".encode()).hexdigest(),
                    })
        traces.write_text("".join(json.dumps(row) + "\n" for row in rows))
        metadata.write_text(json.dumps({
            "estimated_cost_usd": 1.0, "provider": "test-only", "generation_parameters": {"model_id": "claude-sonnet-4-6"},
            "input_provenance": {"source": "test-only"}, "prompt_manifest": {"sha256": "test-only"},
            "scorer_configuration": {"version": "test-only"}, "collection_timestamp": "2026-01-01T00:00:00Z",
            "collection_seed": 1,
            "collector": {"name": "collect_current_model_study.py", "schema_version": 1, "calls": 720},
        }))
        package(traces, output, metadata, 1.0)
        manifest = json.loads((output / "manifest.json").read_text())
        if len(manifest["files"]) != 9 or not all((output / item["path"]).is_file() for item in manifest["files"]):
            raise SystemExit("trace package contract failed")
    print(json.dumps({"trace_packaging": "passed", "records": 720, "cells": 9}))


if __name__ == "__main__":
    main()
