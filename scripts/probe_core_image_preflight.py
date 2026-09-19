"""No-cost contract test for the production Core v1 image preflight."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from verifier.preflight_core_package import ABLATIONS, CELLS, VARIANTS, check


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="core-image-preflight-") as raw:
        root = Path(raw)
        data = root / "paper_reproduction" / "release" / "data"
        release = data.parent
        release.mkdir(parents=True, exist_ok=True)
        (release / "core_parameters.json").write_text(json.dumps({
            "schema_version": 1,
            "delta_item": 0.05, "delta_cap": 0.05, "CI_delta": 0.001, "cred_level": 0.97,
            "conservatism": 5, "draws": 1, "tune": 1, "chains": 1, "cores": 1,
            "random_seed": 1, "reanalysis_interval": 2, "ordinal_tasks": ["ordinal"],
            "continuous_tasks": ["continuous"], "ordinal_max_score": 10,
        }))
        cells = data / "cells"
        cells.mkdir(parents=True)
        files = []
        for cell in sorted(CELLS):
            path = cells / f"{cell}.csv"
            path.write_text("item_id,epoch,score\nitem-1,1,0.5\n")
            files.append({"cell_id": cell, "path": f"cells/{cell}.csv", "sha256": _sha256(path)})
        manifest = {"schema_version": 1, "files": files}
        manifest_path = data / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        private = root / "verifier" / "private_optstop"
        for variant in VARIANTS:
            (private / "hidden" / variant).mkdir(parents=True)
            (private / "hidden" / variant / "manifest.json").write_text("{}")
        reference_cell = {
            "efficiency": 0.0, "full_mean": 0.5, "retained_mean": 0.5,
            "absolute_difference": 0.0, "paired_n": 1,
            "paired_mean_difference": 0.0, "paired_hdi_94": [0.0, 0.0],
            "rope": 0.02, "equivalence_decision": "accept_null", "error": None,
        }
        reference_run = {"cells": {cell: dict(reference_cell) for cell in CELLS}}
        bundle = {
            "schema_version": 1,
            "status": "complete",
            "public_data_manifest_sha256": _sha256(manifest_path),
            "reference_runs": [reference_run] * 20,
            "public_reference": {"cells": {cell: dict(reference_cell) for cell in CELLS}},
            "ablation_reference": {ablation: {} for ablation in ABLATIONS},
            "hidden_variants": [{"id": variant, "reference_runs": [reference_run] * 20} for variant in VARIANTS],
            "scoring_hidden_variant_ids": sorted(VARIANTS),
        }
        (private / "reference_bundle.json").write_text(json.dumps(bundle))
        result = check(root)
        assert result["core_package"] == "passed"
        (cells / "low_binary.csv").write_text("tampered\n")
        try:
            check(root)
        except ValueError as exc:
            assert "hash mismatch" in str(exc)
        else:
            raise AssertionError("tampered data unexpectedly passed image preflight")
    print('{"core_image_preflight": "passed", "tamper_rejected": true}')


if __name__ == "__main__":
    main()
