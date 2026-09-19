"""Validate and package externally collected, non-synthetic optstop traces.

The script intentionally does not call a model API. Run the benchmark harness
outside HUD, then supply its normalised item-by-epoch score JSONL here. This
keeps provider credentials and raw response content out of the HUD image.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


CELLS = tuple(f"{regime}_{score_type}" for score_type in ("binary", "ordinal", "continuous") for regime in ("low", "mid", "high"))
ITEMS_PER_CELL = 20
EPOCHS_PER_ITEM = 4
BUDGET_USD = 50.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    required = {"cell_id", "regime", "score_type", "item_id", "epoch", "score", "model_id", "input_sha256"}
    if not rows or any(not required.issubset(row) for row in rows):
        raise ValueError(f"{path} must contain JSONL rows with {sorted(required)}")
    if any(row["model_id"] != "claude-sonnet-4-6" for row in rows):
        raise ValueError("all records must use claude-sonnet-4-6")
    return rows


def _validate(rows: list[dict[str, Any]], estimated_cost: float) -> dict[str, list[dict[str, Any]]]:
    if estimated_cost > BUDGET_USD:
        raise ValueError(f"estimated collection cost ${estimated_cost:.2f} exceeds the ${BUDGET_USD:.2f} cap")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cell_id = str(row["cell_id"])
        if cell_id not in CELLS:
            raise ValueError(f"unknown cell_id: {cell_id}")
        if cell_id != f"{row['regime']}_{row['score_type']}":
            raise ValueError(f"inconsistent regime/score type for {cell_id}")
        score = float(row["score"])
        if not 0.0 <= score <= (10.0 if row["score_type"] == "ordinal" else 1.0):
            raise ValueError(f"out-of-range score in {cell_id}")
        if row["score_type"] == "ordinal" and score != round(score):
            raise ValueError(f"ordinal score must be an integer category in {cell_id}")
        if not isinstance(row["input_sha256"], str) or len(row["input_sha256"]) != 64:
            raise ValueError(f"input_sha256 must be a SHA-256 digest in {cell_id}")
        grouped[cell_id].append(row)
    if set(grouped) != set(CELLS):
        raise ValueError("study must contain exactly the nine registered cells")
    for cell_id, cell_rows in grouped.items():
        pairs = {(str(row["item_id"]), int(row["epoch"])) for row in cell_rows}
        items = {item for item, _ in pairs}
        if len(cell_rows) != ITEMS_PER_CELL * EPOCHS_PER_ITEM or len(items) != ITEMS_PER_CELL or len(pairs) != ITEMS_PER_CELL * EPOCHS_PER_ITEM:
            raise ValueError(f"{cell_id} must contain {ITEMS_PER_CELL} items x {EPOCHS_PER_ITEM} epochs")
        if any(epoch not in range(1, EPOCHS_PER_ITEM + 1) for _, epoch in pairs):
            raise ValueError(f"{cell_id} has invalid epoch numbering")
        values = {float(row["score"]) for row in cell_rows}
        if len(values) < 2:
            raise ValueError(
                f"{cell_id} has degenerate score support {sorted(values)}; "
                "it cannot support the registered reproduction analysis"
            )
        score_type = cell_id.split("_", maxsplit=1)[1]
        if score_type == "ordinal" and not any(value > 0.0 for value in values):
            raise ValueError(f"{cell_id} has no nonzero ordinal observations")
        if score_type == "continuous" and not any(0.0 < value < 1.0 for value in values):
            raise ValueError(f"{cell_id} has no fractional continuous observations")
    return grouped


def package(input_jsonl: Path, output_dir: Path, collection_metadata: Path, estimated_cost: float) -> None:
    rows = _records(input_jsonl)
    groups = _validate(rows, estimated_cost)
    metadata = json.loads(collection_metadata.read_text())
    if metadata.get("estimated_cost_usd") != estimated_cost:
        raise ValueError("metadata estimated_cost_usd must match --estimated-cost-usd")
    required_metadata = {
        "provider",
        "generation_parameters",
        "input_provenance",
        "prompt_manifest",
        "scorer_configuration",
        "collection_timestamp",
        "collection_seed",
        "collector",
    }
    if not required_metadata.issubset(metadata):
        raise ValueError(f"collection metadata must contain {sorted(required_metadata)}")
    collector = metadata["collector"]
    if (
        collector.get("name") != "collect_current_model_study.py"
        or collector.get("schema_version") != 1
        or collector.get("calls") != ITEMS_PER_CELL * EPOCHS_PER_ITEM * len(CELLS)
    ):
        raise ValueError("collection metadata is not a complete current-model collector attestation")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing trace package: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        cells_dir = staging / "cells"
        cells_dir.mkdir()
        files = []
        for cell_id in sorted(groups):
            path = cells_dir / f"{cell_id}.csv"
            fields = ["regime", "score_type", "item_id", "epoch", "score", "ordinal_max_score", "input_sha256"]
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for row in sorted(groups[cell_id], key=lambda value: (str(value["item_id"]), int(value["epoch"]))):
                    writer.writerow({
                        "regime": row["regime"], "score_type": row["score_type"], "item_id": row["item_id"],
                        "epoch": row["epoch"], "score": row["score"],
                        "ordinal_max_score": 10 if row["score_type"] == "ordinal" else "",
                        "input_sha256": row["input_sha256"],
                    })
            files.append({"cell_id": cell_id, "path": f"cells/{path.name}", "sha256": _sha256(path)})
        manifest = {
            "schema_version": 1,
            "study_id": "optstop-core-reproduction-v1-current-model",
            "model": {"id": "claude-sonnet-4-6", "provider": metadata["provider"], "generation_parameters": metadata["generation_parameters"]},
            "collection": {"items_per_cell": ITEMS_PER_CELL, "epochs_per_item": EPOCHS_PER_ITEM, "budget_usd": BUDGET_USD, "estimated_cost_usd": estimated_cost, "input_provenance": metadata["input_provenance"]},
            "provenance": {
                "prompt_manifest": metadata["prompt_manifest"],
                "scorer_configuration": metadata["scorer_configuration"],
                "collection_timestamp": metadata["collection_timestamp"],
                "collection_seed": metadata["collection_seed"],
                "collector": collector,
            },
            "cells": [{"id": cell_id, "regime": groups[cell_id][0]["regime"], "score_type": groups[cell_id][0]["score_type"]} for cell_id in sorted(groups)],
            "files": files,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staging.replace(output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--collection-metadata", type=Path, required=True)
    parser.add_argument("--estimated-cost-usd", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    package(args.input_jsonl, args.output_dir, args.collection_metadata, args.estimated_cost_usd)


if __name__ == "__main__":
    main()
