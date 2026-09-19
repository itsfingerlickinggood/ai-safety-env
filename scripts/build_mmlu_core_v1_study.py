"""Build the private, deterministic input package for Core Reproduction v1.

The resulting definition and scorer are deliberately external-only.  They
contain MMLU prompts and answer keys needed to collect a new model score-trace
study; neither belongs in the agent workspace or source repository.  HUD later
receives only item/epoch scores and provenance hashes.

The three labels (low, mid, high) are pre-registered *challenge strata* based
on a published subject mapping.  They are not claims about observed model
performance.  The collected outcomes determine whether the strata actually
produce different performance levels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REVISION = "c30699e8356da336a370243923dbaf21066bb9fe"
DATASET = "cais/mmlu"
LICENSE = "MIT"
EXPECTED_TEST_PARQUET_SHA256 = "74a41822ce7d3def56e1682f958469c04642a5336a5ce912fa375fdb90fb25d7"
ITEMS_PER_CELL = 20
ORDINAL_BUNDLE_SIZE = 10
CONTINUOUS_BUNDLE_SIZE = 10

# These are challenge strata, selected before model collection. They are a
# transparent proxy, not an assertion that a current model will score low,
# mid, and high in that order. Each pool supplies substantially more than the
# 420 question records allocated to its three score-type cells.
SUBJECT_POOLS = {
    "low": (
        "elementary_mathematics", "high_school_biology", "high_school_geography",
        "human_aging", "miscellaneous", "nutrition", "prehistory",
    ),
    "mid": (
        "business_ethics", "college_biology", "management", "marketing",
        "machine_learning", "professional_psychology", "sociology",
    ),
    "high": (
        "abstract_algebra", "college_mathematics", "electrical_engineering",
        "formal_logic", "high_school_physics", "jurisprudence", "logical_fallacies",
    ),
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise_row(row: dict[str, Any], row_index: int) -> dict[str, Any]:
    question = row.get("question")
    choices = row.get("choices")
    answer = row.get("answer")
    subject = row.get("subject")
    if not isinstance(question, str) or not question.strip():
        raise ValueError(f"row {row_index}: missing question")
    if not isinstance(choices, list) or len(choices) != 4 or not all(isinstance(value, str) and value.strip() for value in choices):
        raise ValueError(f"row {row_index}: choices must be four non-empty strings")
    if not isinstance(answer, int) or answer not in range(4):
        raise ValueError(f"row {row_index}: answer must be an integer in [0, 3]")
    if not isinstance(subject, str) or not subject:
        raise ValueError(f"row {row_index}: missing subject")
    canonical = {"question": question, "choices": choices, "answer": answer, "subject": subject}
    return {
        **canonical,
        "row_index": row_index,
        "question_sha256": _sha256_bytes(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()),
    }


def _question_block(row: dict[str, Any], number: int) -> str:
    choices = "\n".join(f"{letter}. {choice}" for letter, choice in zip("ABCD", row["choices"], strict=True))
    return f"Question {number}: {row['question']}\n{choices}"


def _item_prompt(rows: list[dict[str, Any]]) -> str:
    blocks = "\n\n".join(_question_block(row, index) for index, row in enumerate(rows, start=1))
    return (
        "Answer each independent multiple-choice question. Choose exactly one of A, B, C, or D for each. "
        f"Return only {len(rows)} comma-separated letters, with no explanation or markup. "
        f"Example format: {','.join('A' for _ in rows)}\n\n{blocks}"
    )


def _allocate(rows: list[dict[str, Any]], regime: str, seed: int) -> dict[str, list[list[dict[str, Any]]]]:
    needed = ITEMS_PER_CELL * (1 + ORDINAL_BUNDLE_SIZE + CONTINUOUS_BUNDLE_SIZE)
    rng = random.Random(f"optstop-core-v1:{seed}:{regime}")
    ordered = list(rows)
    rng.shuffle(ordered)
    if len(ordered) < needed:
        raise ValueError(f"{regime} source pool has {len(ordered)} usable questions; needs {needed}")
    cursor = 0
    binary = [[ordered[cursor + index]] for index in range(ITEMS_PER_CELL)]
    cursor += ITEMS_PER_CELL
    ordinal = [ordered[cursor + index * ORDINAL_BUNDLE_SIZE: cursor + (index + 1) * ORDINAL_BUNDLE_SIZE] for index in range(ITEMS_PER_CELL)]
    cursor += ITEMS_PER_CELL * ORDINAL_BUNDLE_SIZE
    continuous = [ordered[cursor + index * CONTINUOUS_BUNDLE_SIZE: cursor + (index + 1) * CONTINUOUS_BUNDLE_SIZE] for index in range(ITEMS_PER_CELL)]
    return {"binary": binary, "ordinal": ordinal, "continuous": continuous}


def build_definition(rows: Iterable[dict[str, Any]], *, source_sha256: str, selection_seed: int) -> dict[str, Any]:
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, raw in enumerate(rows):
        row = _normalise_row(raw, index)
        by_subject[row["subject"]].append(row)
    allocated: dict[str, dict[str, list[list[dict[str, Any]]]]] = {}
    for regime, subjects in SUBJECT_POOLS.items():
        pool = [row for subject in subjects for row in by_subject[subject]]
        allocated[regime] = _allocate(pool, regime, selection_seed)

    items: list[dict[str, Any]] = []
    for regime in ("low", "mid", "high"):
        for score_type in ("binary", "ordinal", "continuous"):
            for index, bundle in enumerate(allocated[regime][score_type], start=1):
                items.append({
                    "cell_id": f"{regime}_{score_type}",
                    "regime": regime,
                    "score_type": score_type,
                    "item_id": f"mmlu-{regime}-{score_type}-{index:02d}",
                    "prompt": _item_prompt(bundle),
                    "answer_keys": ["ABCD"[int(row["answer"])] for row in bundle],
                    "source_records": [
                        {
                            "subject": row["subject"],
                            "row_index": row["row_index"],
                            "question_sha256": row["question_sha256"],
                        }
                        for row in bundle
                    ],
                })
    return {
        "schema_version": 1,
        "study_id": "optstop-core-reproduction-v1-mmlu-current-model",
        "model_id": "claude-sonnet-4-6",
        "collection_seed": selection_seed,
        "source": {
            "dataset": DATASET,
            "revision": REVISION,
            "split": "all/test",
            "license": LICENSE,
            "source_file_sha256": source_sha256,
            "challenge_strata": {
                regime: {"subjects": list(subjects), "interpretation": "pre-registered challenge stratum, not an observed performance label"}
                for regime, subjects in SUBJECT_POOLS.items()
            },
        },
        "items": items,
    }


SCORER = '''"""Deterministic MMLU bundled-item scorer; keep this file private."""
from __future__ import annotations

import re


def _answers(completion: str, expected_count: int) -> list[str] | None:
    """Read an exact answer list, tolerating harmless presentation markup.

    The prompt asks for a bare comma-separated list. The fallbacks avoid
    turning ordinary prose into answers: every accepted candidate must contain
    exactly the required number of A-D tokens.
    """
    text = completion.upper()
    candidates = re.findall(r"<ANSWERS>\\s*(.*?)\\s*</ANSWERS>", text, flags=re.DOTALL)
    candidates.extend(re.findall(
        r"(?<![A-Z])([A-D](?:\\s*(?:,|;|/|\\||\\s)\\s*[A-D]){%d})(?![A-Z])" % (expected_count - 1),
        text,
    ))
    for candidate in reversed(candidates):
        values = re.findall(r"[A-D]", candidate)
        if len(values) == expected_count:
            return values
    numbered = re.findall(r"(?:^|[\\n,;])\\s*(?:\\d+\\s*[.)]\\s*)?([A-D])(?=\\s*(?:[,;\\n]|$))", text)
    if len(numbered) == expected_count:
        return numbered
    return None


def score(item: dict, completion: str) -> float:
    expected = item["answer_keys"]
    answers = _answers(completion, len(expected))
    if answers is None:
        return 0.0
    correct = sum(actual == target for actual, target in zip(answers, expected, strict=True))
    if item["score_type"] == "binary":
        return float(correct == 1)
    if item["score_type"] == "ordinal":
        return float(correct)
    return correct / len(expected)
'''


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "pyarrow is required only for this external builder. Run it with "
            "`uv run --with pyarrow==17.0.0 python scripts/build_mmlu_core_v1_study.py ...`"
        ) from exc
    return pq.read_table(path).to_pylist()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mmlu-test-parquet", type=Path, required=True)
    parser.add_argument("--selection-seed", type=int, default=20260905)
    parser.add_argument("--output-definition", type=Path, required=True)
    parser.add_argument("--output-scorer", type=Path, required=True)
    args = parser.parse_args()
    if args.output_definition.exists() or args.output_scorer.exists():
        raise SystemExit("refusing to overwrite an external study definition or scorer")
    source_sha256 = _sha256_file(args.mmlu_test_parquet)
    if source_sha256 != EXPECTED_TEST_PARQUET_SHA256:
        raise SystemExit(
            "MMLU parquet hash does not match the pinned Core v1 snapshot; "
            f"expected {EXPECTED_TEST_PARQUET_SHA256}, got {source_sha256}"
        )
    rows = _read_parquet(args.mmlu_test_parquet)
    definition = build_definition(rows, source_sha256=source_sha256, selection_seed=args.selection_seed)
    if len(definition["items"]) != 180:
        raise AssertionError("internal error: expected 180 study items")
    args.output_definition.parent.mkdir(parents=True, exist_ok=True)
    args.output_scorer.parent.mkdir(parents=True, exist_ok=True)
    args.output_definition.write_text(json.dumps(definition, indent=2) + "\n")
    args.output_scorer.write_text(textwrap.dedent(SCORER))
    print(json.dumps({
        "study_definition": str(args.output_definition),
        "scorer": str(args.output_scorer),
        "items": len(definition["items"]),
        "source": definition["source"],
        "warning": "keep these files outside the repository and HUD agent workspace",
    }, indent=2))


if __name__ == "__main__":
    main()
