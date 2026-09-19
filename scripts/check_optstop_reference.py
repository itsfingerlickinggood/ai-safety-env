"""Preflight the optstop Core Reproduction v1 package without running MCMC."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper_reproduction" / "phase1" / "paper_redacted.md"
PROVENANCE = ROOT / "paper_reproduction" / "phase1" / "paper_provenance.json"
RELEASE = ROOT / "paper_reproduction" / "release"
PRIVATE = ROOT / "verifier" / "private_optstop" / "reference_bundle.json"
CELLS = {
    f"{regime}_{score_type}"
    for score_type in ("binary", "ordinal", "continuous")
    for regime in ("low", "mid", "high")
}
ABLATIONS = {"fixed_budget_baseline", "item_order_sensitivity", "stopping_conservatism_sensitivity"}
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


def _trace_package_is_valid(data: Path) -> bool:
    try:
        manifest = json.loads((data / "manifest.json").read_text())
        declared = {str(entry["id"]) for entry in manifest["cells"]}
        files = {str(entry["cell_id"]): entry for entry in manifest["files"]}
        return (
            manifest.get("schema_version") == 1
            and manifest["model"]["id"] == "claude-sonnet-4-6"
            and manifest["collection"]["items_per_cell"] == 20
            and manifest["collection"]["epochs_per_item"] == 4
            and set(files) == CELLS == declared
            and all((data / entry["path"]).is_file() and _sha256(data / entry["path"]) == entry["sha256"] for entry in files.values())
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _private_reference_is_valid(data: Path) -> bool:
    try:
        bundle = json.loads(PRIVATE.read_text())
        variants = {str(entry["id"]) for entry in bundle["hidden_variants"]}
        return (
            bundle.get("schema_version") == 1
            and bundle.get("status") == "complete"
            and bundle["public_data_manifest_sha256"] == _sha256(data / "manifest.json")
            and len(bundle["hidden_selection_salt"]) == 64
            and len(bundle["reference_runs"]) == 20
            and set(bundle["public_reference"]["cells"]) == CELLS
            and all(set(bundle["public_reference"]["cells"][cell]) == REFERENCE_CELL_FIELDS for cell in CELLS)
            and all(set(run["cells"][cell]) == REFERENCE_CELL_FIELDS for run in bundle["reference_runs"] for cell in CELLS)
            and all(run["cells"][cell].get("error") is None for run in bundle["reference_runs"] for cell in CELLS)
            and set(bundle["ablation_reference"]) == ABLATIONS
            and {"row_order", "item_ids", "unequal_observations", "sparse", "score_scale", "threshold_stress", "nonreplication"}.issubset(variants)
            and all(len(entry.get("reference_runs", [])) == 20 for entry in bundle["hidden_variants"])
            and len(set(map(str, bundle.get("scoring_hidden_variant_ids", [])))) >= 3
            and set(map(str, bundle.get("scoring_hidden_variant_ids", []))).issubset(variants)
            and set(bundle["tolerances"]["cells"]) == CELLS
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase-one-only", action="store_true")
    args = parser.parse_args()
    paper = PAPER.read_text()
    provenance = json.loads(PROVENANCE.read_text())
    blocked = (
        "57.2%", "97.3%", "81.1%", "mean absolute score deviation was 0.006", "accept-null verdict",
        "twenty-nine validation runs", "all runs meeting their specified stopping criteria",
        "producing scores consistent with benchmark expectations",
    )
    leaks = [needle for needle in blocked if needle.lower() in paper.lower()]
    redacted_sections = re.findall(r"<!-- Source page (\d+) -->\n(.*?)(?=\n<!-- Source page|\Z)", paper, flags=re.S)
    fully_withheld_pages = {str(page) for page in (*range(6, 9), *range(20, 33))}
    malformed_redactions = [
        page for page, section in redacted_sections
        if page in fully_withheld_pages and section.strip().count("\n") > 1
    ]
    checks = {
        "source_derived_redacted_paper": len(paper.split()) > 5000 and "[RESULTS REDACTED" in paper,
        "source_hash": len(str(provenance.get("source_pdf_sha256", ""))) == 64,
        "no_known_result_leaks": not leaks,
        "redaction_blocks_are_placeholders": not malformed_redactions,
        "analysis_manifest": (RELEASE / "analysis_manifest.json").is_file(),
        "core_parameters": (RELEASE / "core_parameters.json").is_file(),
        "single_vendor_commit": (ROOT / "paper_reproduction" / "vendor" / "OPTSTOP_COMMIT").is_file(),
    }
    if not args.phase_one_only:
        data = RELEASE / "data"
        checks["trace_package"] = _trace_package_is_valid(data)
        checks["private_reference"] = _private_reference_is_valid(data)
    print(json.dumps({"checks": checks, "paper_sha256": _sha256(PAPER), "leaks": leaks, "malformed_redactions": malformed_redactions}, indent=2))
    if not all(checks.values()):
        raise SystemExit("optstop preflight failed")


if __name__ == "__main__":
    main()
