"""No-network contract test for the external MMLU Core v1 study builder."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_mmlu_core_v1_study import SUBJECT_POOLS, SCORER, build_definition  # noqa: E402


def main() -> None:
    rows = []
    for subject_index, subject in enumerate(subject for subjects in SUBJECT_POOLS.values() for subject in subjects):
        for row_index in range(110):
            rows.append({
                "question": f"Question {subject_index}/{row_index}",
                "choices": ["zero", "one", "two", "three"],
                "answer": row_index % 4,
                "subject": subject,
            })
    definition = build_definition(rows, source_sha256=hashlib.sha256(b"synthetic-source-for-contract-test").hexdigest(), selection_seed=7)
    assert len(definition["items"]) == 180
    assert {item["cell_id"] for item in definition["items"]} == {
        f"{regime}_{score_type}"
        for regime in ("low", "mid", "high")
        for score_type in ("binary", "ordinal", "continuous")
    }
    first = next(item for item in definition["items"] if item["score_type"] == "ordinal")
    with tempfile.TemporaryDirectory(prefix="mmlu-scorer-probe-") as raw:
        scorer_path = Path(raw) / "scorer.py"
        scorer_path.write_text(SCORER)
        spec = importlib.util.spec_from_file_location("probe_scorer", scorer_path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        answer = ",".join(first["answer_keys"])
        assert module.score(first, f"<answers>{answer}</answers>") == 10.0
        assert module.score(first, "A") == 0.0
    print('{"mmlu_study_builder": "passed", "items": 180, "ordinal_bundle_size": 10, "continuous_bundle_size": 10}')


if __name__ == "__main__":
    main()
