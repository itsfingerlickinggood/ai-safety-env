"""Fail a production image build unless its Core v1 evidence bundle is complete.

This verifier-side check intentionally has no dependency on developer-only
scripts. It runs as root while the image is built, before the verifier tree is
made unreadable to the agent UID.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


CELLS = {
    f"{regime}_{score_type}"
    for regime in ("low", "mid", "high")
    for score_type in ("binary", "ordinal", "continuous")
}
VARIANTS = {
    "row_order", "item_ids", "unequal_observations", "sparse", "score_scale",
    "threshold_stress", "nonreplication",
}
ABLATIONS = {
    "fixed_budget_baseline", "item_order_sensitivity", "stopping_conservatism_sensitivity",
}
REFERENCE_CELL_FIELDS = {
    "efficiency", "full_mean", "retained_mean", "absolute_difference", "paired_n",
    "paired_mean_difference", "paired_hdi_94", "rope", "equivalence_decision", "error",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"missing required file: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def check(root: Path) -> dict[str, object]:
    data = root / "paper_reproduction" / "release" / "data"
    parameters = _read_json(root / "paper_reproduction" / "release" / "core_parameters.json")
    required_parameters = {
        "delta_item", "delta_cap", "CI_delta", "cred_level", "conservatism", "draws", "tune",
        "chains", "cores", "random_seed", "reanalysis_interval", "ordinal_tasks",
        "continuous_tasks", "ordinal_max_score",
    }
    if parameters.get("schema_version") != 1 or not required_parameters.issubset(parameters):
        raise ValueError("release core_parameters.json is incomplete")
    manifest_path = data / "manifest.json"
    manifest = _read_json(manifest_path)
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, list):
        raise ValueError("public data manifest has an invalid schema")
    by_cell = {str(entry.get("cell_id")): entry for entry in files if isinstance(entry, dict)}
    if set(by_cell) != CELLS:
        raise ValueError("public data manifest must contain exactly the nine Core v1 cells")
    for cell, entry in by_cell.items():
        relative = Path(str(entry.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("cells",):
            raise ValueError(f"unsafe or invalid data path for {cell}")
        source = data / relative
        if not source.is_file() or _sha256(source) != entry.get("sha256"):
            raise ValueError(f"public data hash mismatch for {cell}")

    private = root / "verifier" / "private_optstop"
    bundle = _read_json(private / "reference_bundle.json")
    if bundle.get("schema_version") != 1 or bundle.get("status") != "complete":
        raise ValueError("private reference bundle is absent or incomplete")
    if bundle.get("public_data_manifest_sha256") != _sha256(manifest_path):
        raise ValueError("private reference bundle is for different public score traces")
    if len(bundle.get("reference_runs", [])) != 20:
        raise ValueError("private reference bundle must contain 20 reference runs")
    if any(run.get("cells", {}).get(cell, {}).get("error") is not None for run in bundle["reference_runs"] for cell in CELLS):
        raise ValueError("private public reference includes stopping or inference errors")
    if set(bundle.get("public_reference", {}).get("cells", {})) != CELLS:
        raise ValueError("private public reference lacks a Core v1 cell")
    if any(set(bundle["public_reference"]["cells"][cell]) != REFERENCE_CELL_FIELDS for cell in CELLS):
        raise ValueError("private public reference uses an outdated cell-result schema")
    if any(set(run.get("cells", {}).get(cell, {})) != REFERENCE_CELL_FIELDS for run in bundle["reference_runs"] for cell in CELLS):
        raise ValueError("private reference runs use an outdated cell-result schema")
    if set(bundle.get("ablation_reference", {})) != ABLATIONS:
        raise ValueError("private reference lacks a registered ablation")
    variants = {str(value.get("id")) for value in bundle.get("hidden_variants", []) if isinstance(value, dict)}
    if not VARIANTS.issubset(variants):
        raise ValueError("private reference lacks a required hidden variant")
    scoring_variants = {str(value) for value in bundle.get("scoring_hidden_variant_ids", [])}
    if len(scoring_variants) < 3 or not scoring_variants.issubset(variants):
        raise ValueError("private reference lacks three discriminative hidden scoring variants")
    for variant in bundle.get("hidden_variants", []):
        runs = variant.get("reference_runs", []) if isinstance(variant, dict) else []
        if len(runs) != 20 or any(set(run.get("cells", {}).get(cell, {})) != REFERENCE_CELL_FIELDS for run in runs for cell in CELLS):
            raise ValueError("hidden variant lacks measured per-cell seed variation")
    for variant in variants:
        if not (private / "hidden" / variant / "manifest.json").is_file():
            raise ValueError(f"hidden input package missing for {variant}")
    return {
        "core_package": "passed",
        "public_manifest_sha256": _sha256(manifest_path),
        "cells": len(CELLS),
        "hidden_variants": len(variants),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(check(args.root), sort_keys=True))


if __name__ == "__main__":
    main()
