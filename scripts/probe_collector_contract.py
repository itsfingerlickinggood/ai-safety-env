"""No-cost validation of the external study collector's schema and budget gate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.collect_current_model_study import _canonical_hash, _estimate_cost, _load_checkpoint, _load_definition


def main() -> None:
    cells = [
        f"{regime}_{score_type}"
        for score_type in ("binary", "ordinal", "continuous")
        for regime in ("low", "mid", "high")
    ]
    definition = {
        "schema_version": 1,
        "study_id": "contract-probe",
        "model_id": "claude-sonnet-4-6",
        "source": "test-only; never package this data",
        "items": [
            {
                "cell_id": cell,
                "regime": cell.split("_", 1)[0],
                "score_type": cell.split("_", 1)[1],
                "item_id": f"item-{index}",
                "prompt": "Return a concise answer.",
            }
            for cell in cells for index in range(20)
        ],
    }
    with tempfile.TemporaryDirectory(prefix="optstop-collector-contract-") as raw:
        path = Path(raw) / "definition.json"
        path.write_text(json.dumps(definition))
        loaded = _load_definition(path)
        estimate = _estimate_cost(loaded, max_output_tokens=64, input_price_per_million=3.0, output_price_per_million=15.0)
        if not 0.0 < estimate < 50.0:
            raise SystemExit(f"unexpected conservative estimate: {estimate}")
        first = loaded["items"][0]
        checkpoint = Path(raw) / "checkpoint.jsonl"
        checkpoint.write_text(json.dumps({
            "cell_id": first["cell_id"], "regime": first["regime"], "score_type": first["score_type"],
            "item_id": first["item_id"], "epoch": 1, "score": 0.0,
            "model_id": "claude-sonnet-4-6",
            "input_sha256": _canonical_hash({key: first[key] for key in ("cell_id", "item_id", "prompt", "regime", "score_type")}),
        }) + "\n")
        if len(_load_checkpoint(checkpoint, loaded)) != 1:
            raise SystemExit("valid scored-only checkpoint did not load")
        checkpoint.write_text(checkpoint.read_text() + checkpoint.read_text())
        try:
            _load_checkpoint(checkpoint, loaded)
        except ValueError:
            pass
        else:
            raise SystemExit("duplicate checkpoint record unexpectedly passed")
        definition["items"].pop()
        path.write_text(json.dumps(definition))
        try:
            _load_definition(path)
        except ValueError:
            pass
        else:
            raise SystemExit("incomplete study definition unexpectedly passed")
    print(json.dumps({"collector_contract": "passed", "calls": 720, "estimated_cost_usd": estimate}))


if __name__ == "__main__":
    main()
