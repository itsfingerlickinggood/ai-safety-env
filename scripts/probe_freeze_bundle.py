"""No-cost schema test for the private reference freezer.

The Bayesian engine is replaced only in this test so it verifies bundle shape,
private variants, ablation references, and tolerances without claiming to test
scientific correctness on synthetic observations.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import scripts.freeze_optstop_reference as freezer


def _fake_reference(data_root: Path, seed: int, **_: object) -> dict[str, object]:
    offset = 0.0 if data_root.name == "data" else 0.05
    cells = {
        cell: {
            "efficiency": 0.4 + offset + (seed % 3) * 0.001,
            "full_mean": 0.5,
            "retained_mean": 0.5,
            "absolute_difference": 0.0,
            "paired_n": 20,
            "paired_mean_difference": 0.0,
            "paired_hdi_94": [-0.01, 0.01],
            "rope": 0.02,
            "equivalence_decision": "accept_null",
            "error": None,
        }
        for cell in freezer.CELLS
    }
    return {"cells": cells, "mean_efficiency": 0.4 + offset, "mean_absolute_difference": 0.0, "overall_equivalence_decision": "accept_null"}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="optstop-freeze-contract-") as raw:
        root = Path(raw)
        data = root / "data"
        cells = data / "cells"
        cells.mkdir(parents=True)
        files = []
        for cell in freezer.CELLS:
            regime, score_type = cell.split("_", 1)
            pd.DataFrame({
                "regime": [regime] * 80, "score_type": [score_type] * 80,
                "item_id": [f"item-{index // 4}" for index in range(80)], "epoch": [(index % 4) + 1 for index in range(80)],
                "score": [5 if score_type == "ordinal" else 0.5] * 80,
            }).to_csv(cells / f"{cell}.csv", index=False)
            path = cells / f"{cell}.csv"
            files.append({"cell_id": cell, "path": f"cells/{cell}.csv", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        (data / "manifest.json").write_text(json.dumps({
            "collection": {"items_per_cell": 20, "epochs_per_item": 4},
            "files": files,
        }))
        original = freezer._reference
        freezer._reference = _fake_reference
        try:
            freezer.freeze(data, root / "private")
        finally:
            freezer._reference = original
        bundle = json.loads((root / "private" / "reference_bundle.json").read_text())
        if (
            len(bundle["reference_runs"]) != 20
            or len(bundle["hidden_variants"]) != 7
            or len(bundle["ablation_reference"]) != 3
            or len(bundle["scoring_hidden_variant_ids"]) < 3
        ):
            raise SystemExit("private reference bundle contract failed")
        if any(len(variant.get("reference_runs", [])) != 20 for variant in bundle["hidden_variants"]):
            raise SystemExit("hidden variants do not have measured seed variation")
        decisions = {
            cell: {**bundle["public_reference"]["cells"][cell], "equivalence_decision": "reject"}
            for cell in freezer.CELLS
        }
        if freezer._aggregate_equivalence(decisions) != "reject":
            raise SystemExit("aggregate equivalence accepted a rejecting cell")
        for variant in bundle["hidden_variants"]:
            hidden = root / "private" / "hidden" / str(variant["id"])
            manifest = json.loads((hidden / "manifest.json").read_text())
            for entry in manifest["files"]:
                path = hidden / str(entry["path"])
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                    raise SystemExit(f"hidden variant has a stale manifest hash: {variant['id']}")
        def fail_reference(*_: object, **__: object) -> dict[str, object]:
            raise RuntimeError("intentional reference failure")
        freezer._reference = fail_reference
        failed_output = root / "failed-private"
        try:
            freezer.freeze(data, failed_output)
        except RuntimeError as exc:
            if "intentional reference failure" not in str(exc):
                raise
        else:
            raise SystemExit("intentional freeze failure unexpectedly succeeded")
        finally:
            freezer._reference = original
        if failed_output.exists() or list(root.glob(".failed-private.staging-*")):
            raise SystemExit("failed reference freeze left retry-blocking output")
    print(json.dumps({"freeze_bundle": "passed", "reference_seeds": 20, "hidden_variants": 7, "ablations": 3}))


if __name__ == "__main__":
    main()
