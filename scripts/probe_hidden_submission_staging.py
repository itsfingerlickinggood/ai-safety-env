"""Exercise the hidden-submission staging path without PyMC or model calls."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import verifier.optstop_score as scorer


def _reference() -> dict[str, object]:
    cells = {
        cell: {
            "efficiency": 0.4,
            "full_mean": 0.5,
            "retained_mean": 0.5,
            "absolute_difference": 0.0,
            "paired_n": 1,
            "paired_mean_difference": 0.0,
            "paired_hdi_94": [0.0, 0.0],
            "rope": 0.02,
            "equivalence_decision": "accept_null",
        }
        for cell in scorer._manifest_ids()
        if "sensitivity" not in cell and "baseline" not in cell
    }
    return {"cells": cells}


def main() -> None:
    original_private = scorer.PRIVATE
    original_force = os.environ.get("HUD_FORCE_UNSANDBOXED_GRADER")
    with tempfile.TemporaryDirectory(prefix="hidden-submission-staging-") as raw:
        root = Path(raw)
        workspace = root / "workspace"
        workspace.mkdir()
        private = root / "private"
        hidden = private / "hidden" / "fixture"
        (hidden / "cells").mkdir(parents=True)
        for cell in _reference()["cells"]:
            (hidden / "cells" / f"{cell}.csv").write_text("item_id,epoch,score\nitem-1,1,0.5\n")
        (hidden / "manifest.json").write_text("{}")
        script = '''
import argparse, csv, json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input-dir", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if not (args.input_dir / "manifest.json").is_file():
    raise SystemExit("hidden manifest was not staged")
cells = {}
for path in sorted((args.input_dir / "cells").glob("*.csv")):
    with path.open() as stream:
        next(csv.reader(stream))
    cells[path.stem] = {"efficiency": 0.4, "full_mean": 0.5, "retained_mean": 0.5, "absolute_difference": 0.0, "paired_n": 1, "paired_mean_difference": 0.0, "paired_hdi_94": [0.0, 0.0], "rope": 0.02, "equivalence_decision": "accept_null", "error": None}
args.output.write_text(json.dumps({"schema_version": 1, "cells": cells, "mean_efficiency": 0.4, "mean_absolute_difference": 0.0, "overall_equivalence_decision": "accept_null"}))
'''
        (workspace / "submission.py").write_text(script)
        bundle = {
            "hidden_selection_salt": "0" * 64,
            "hidden_variants": [{"id": "fixture", "reference": _reference(), "tolerances": {"cells": {
                cell: {metric: 0.01 for metric in ("efficiency", "full_mean", "retained_mean", "absolute_difference", "paired_mean_difference", "paired_hdi_lower", "paired_hdi_upper")}
                for cell in _reference()["cells"]
            }} }],
        }
        scorer.PRIVATE = private
        os.environ["HUD_FORCE_UNSANDBOXED_GRADER"] = "1"
        value, note = scorer._hidden_score(workspace, bundle)
        assert value == 1.0 and note == "fixture", (value, note)
    scorer.PRIVATE = original_private
    if original_force is None:
        os.environ.pop("HUD_FORCE_UNSANDBOXED_GRADER", None)
    else:
        os.environ["HUD_FORCE_UNSANDBOXED_GRADER"] = original_force
    print('{"hidden_submission_staging": "passed", "hidden_score": 1.0}')


if __name__ == "__main__":
    main()
