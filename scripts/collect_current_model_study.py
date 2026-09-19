"""Collect a bounded, provenance-recorded current-model optstop study.

This program runs outside the HUD environment. It never writes API keys or
raw model completions to the repository. Instead it writes the normalized
item/epoch score JSONL consumed by ``prepare_current_model_study.py``.

The caller supplies a pinned 180-item study definition and a local scoring
function. This is intentional: inventing benchmark items or treating a model's
self-reported score as ground truth would make the reproduction invalid.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from datetime import UTC, datetime
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from anthropic import Anthropic


CELLS = tuple(
    f"{regime}_{score_type}"
    for score_type in ("binary", "ordinal", "continuous")
    for regime in ("low", "mid", "high")
)
ITEMS_PER_CELL = 20
EPOCHS_PER_ITEM = 4
MAX_BUDGET_USD = 50.0
HUD_GATEWAY_URL = "https://inference.hud.ai"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _load_definition(path: Path) -> dict[str, Any]:
    definition = json.loads(path.read_text())
    if definition.get("schema_version") != 1 or definition.get("model_id") != "claude-sonnet-4-6":
        raise ValueError("study definition must be schema_version 1 for claude-sonnet-4-6")
    items = definition.get("items")
    if not isinstance(items, list):
        raise ValueError("study definition must provide an items list")
    counts = Counter(str(item.get("cell_id")) for item in items)
    if set(counts) != set(CELLS) or any(counts[cell] != ITEMS_PER_CELL for cell in CELLS):
        raise ValueError("study definition must contain exactly 20 items for each registered cell")
    identifiers = [(str(item.get("cell_id")), str(item.get("item_id"))) for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("item_id values must be unique within each cell")
    for item in items:
        cell = str(item["cell_id"])
        regime, score_type = cell.split("_", maxsplit=1)
        if item.get("regime") != regime or item.get("score_type") != score_type:
            raise ValueError(f"inconsistent cell metadata for {cell}/{item.get('item_id')}")
        if not isinstance(item.get("prompt"), str) or not item["prompt"].strip():
            raise ValueError(f"missing prompt for {cell}/{item.get('item_id')}")
    return definition


def _load_scorer(path: Path) -> Callable[[dict[str, Any], str], float]:
    spec = importlib.util.spec_from_file_location("optstop_external_scorer", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load scorer module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scorer = getattr(module, "score", None)
    if not callable(scorer):
        raise ValueError("scorer module must define score(item: dict, completion: str) -> float")
    return scorer


def _build_client(provider: str) -> tuple[Anthropic, str]:
    """Build an external client without persisting its credential.

    HUD's inference gateway accepts the Anthropic Messages protocol. This is
    used only while assembling the private trace package; the evaluated HUD
    environment remains offline and receives neither credential.
    """
    if provider == "hud-gateway":
        key = os.environ.get("HUD_API_KEY")
        if not key:
            # ``hud set`` persists this value in HUD's own settings file rather
            # than exporting it into the current shell. Reuse that supported
            # lookup so either HUD authentication method works for collection.
            from hud.settings import settings

            key = settings.api_key
        if not key:
            raise RuntimeError("set HUD_API_KEY with `hud set HUD_API_KEY=...` or export it for --provider hud-gateway")
        return Anthropic(
            api_key=key,
            base_url=os.environ.get("HUD_GATEWAY_URL", HUD_GATEWAY_URL),
        ), "HUD inference gateway"
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY must be set in the external collection shell for --provider anthropic")
    return Anthropic(api_key=key), "Anthropic Messages API"


def _estimate_cost(definition: dict[str, Any], *, max_output_tokens: int, input_price_per_million: float, output_price_per_million: float) -> float:
    # Conservative byte/4 estimate. The price parameters are recorded in the
    # output metadata, so the estimate can be reproduced and audited.
    input_tokens = sum(math.ceil(len(item["prompt"].encode("utf-8")) / 4) for item in definition["items"])
    calls = len(definition["items"]) * EPOCHS_PER_ITEM
    return (input_tokens * EPOCHS_PER_ITEM / 1_000_000 * input_price_per_million) + (calls * max_output_tokens / 1_000_000 * output_price_per_million)


def _score(item: dict[str, Any], completion: str, scorer: Callable[[dict[str, Any], str], float]) -> float:
    value = float(scorer(item, completion))
    upper = 10.0 if item["score_type"] == "ordinal" else 1.0
    if not math.isfinite(value) or not 0.0 <= value <= upper:
        raise ValueError(f"scorer returned invalid score for {item['cell_id']}/{item['item_id']}")
    if item["score_type"] == "ordinal" and value != round(value):
        raise ValueError(f"scorer returned non-integer ordinal score for {item['cell_id']}/{item['item_id']}")
    return value


def _validate_score_support(records: list[dict[str, Any]]) -> None:
    """Reject a frozen package that does not exercise its advertised scores."""
    by_cell: dict[str, set[float]] = {}
    for record in records:
        by_cell.setdefault(str(record["cell_id"]), set()).add(float(record["score"]))
    failures: list[str] = []
    for cell in CELLS:
        values = by_cell.get(cell, set())
        if len(values) < 2:
            failures.append(f"{cell}: fewer than two observed score values ({sorted(values)})")
            continue
        score_type = cell.split("_", maxsplit=1)[1]
        if score_type == "ordinal" and not any(value > 0.0 for value in values):
            failures.append(f"{cell}: ordinal score support contains no nonzero value")
        if score_type == "continuous" and not any(0.0 < value < 1.0 for value in values):
            failures.append(f"{cell}: continuous score support contains no fractional value")
    if failures:
        raise RuntimeError(
            "collected traces do not support the registered 3x3 score study; "
            "do not finalize them. " + "; ".join(failures)
        )


def _record_key(record: dict[str, Any]) -> tuple[str, str, int]:
    """Return the unique trace coordinate, validating a checkpoint record."""
    required = {"cell_id", "item_id", "epoch", "score", "model_id", "input_sha256"}
    if not required.issubset(record):
        raise ValueError("existing checkpoint contains an invalid trace record")
    if record["model_id"] != "claude-sonnet-4-6":
        raise ValueError("existing checkpoint was collected with a different model")
    epoch = int(record["epoch"])
    if epoch not in range(1, EPOCHS_PER_ITEM + 1):
        raise ValueError("existing checkpoint contains an invalid epoch")
    return str(record["cell_id"]), str(record["item_id"]), epoch


def _load_checkpoint(path: Path, definition: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    """Load a scored-only JSONL checkpoint and reject mismatched definitions."""
    expected_hashes = {
        (str(item["cell_id"]), str(item["item_id"])): _canonical_hash(
            {key: item[key] for key in ("cell_id", "item_id", "prompt", "regime", "score_type")}
        )
        for item in definition["items"]
    }
    checkpoint: dict[tuple[str, str, int], dict[str, Any]] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        cell_id, item_id, epoch = _record_key(record)
        if expected_hashes.get((cell_id, item_id)) != record["input_sha256"]:
            raise ValueError("existing checkpoint does not match this study definition")
        key = (cell_id, item_id, epoch)
        if key in checkpoint:
            raise ValueError("existing checkpoint contains duplicate item/epoch records")
        checkpoint[key] = record
    return checkpoint


def collect(
    definition: dict[str, Any],
    scorer: Callable[[dict[str, Any], str], float],
    *,
    output: Path,
    metadata_output: Path,
    max_output_tokens: int,
    input_price_per_million: float,
    output_price_per_million: float,
    dry_run: bool,
    resume: bool,
    provider: str,
) -> None:
    estimate = _estimate_cost(
        definition,
        max_output_tokens=max_output_tokens,
        input_price_per_million=input_price_per_million,
        output_price_per_million=output_price_per_million,
    )
    if estimate > MAX_BUDGET_USD:
        raise ValueError(f"conservative trace-collection estimate ${estimate:.2f} exceeds ${MAX_BUDGET_USD:.2f}")
    if metadata_output.exists():
        raise FileExistsError("refusing to overwrite completed collection metadata")
    if output.exists() and not resume:
        raise FileExistsError("trace output already exists; use --resume to continue its validated checkpoint")
    if dry_run:
        print(json.dumps({"dry_run": True, "calls": len(definition["items"]) * EPOCHS_PER_ITEM, "estimated_cost_usd": estimate}, indent=2))
        return
    client, provider_label = _build_client(provider)
    checkpoint = _load_checkpoint(output, definition) if output.exists() else {}
    output.parent.mkdir(parents=True, exist_ok=True)
    expected_calls = len(definition["items"]) * EPOCHS_PER_ITEM
    if len(checkpoint) > expected_calls:
        raise ValueError("existing checkpoint has more records than the registered study")
    records: list[dict[str, Any]] = list(checkpoint.values())
    # Line-buffered appends make every scored record recoverable after a
    # transient failure, while raw model completions remain process-local.
    with output.open("a", encoding="utf-8", buffering=1) as stream:
        for item in sorted(definition["items"], key=lambda row: (row["cell_id"], str(row["item_id"]))):
            input_hash = _canonical_hash({key: item[key] for key in ("cell_id", "item_id", "prompt", "regime", "score_type")})
            for epoch in range(1, EPOCHS_PER_ITEM + 1):
                if (str(item["cell_id"]), str(item["item_id"]), epoch) in checkpoint:
                    continue
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=max_output_tokens,
                    messages=[{"role": "user", "content": item["prompt"]}],
                )
                completion = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
                record = {
                    "cell_id": item["cell_id"], "regime": item["regime"], "score_type": item["score_type"],
                    "item_id": item["item_id"], "epoch": epoch, "score": _score(item, completion, scorer),
                    "model_id": "claude-sonnet-4-6", "input_sha256": input_hash,
                }
                stream.write(json.dumps(record, sort_keys=True) + "\n")
                records.append(record)
    if len(records) != expected_calls:
        raise RuntimeError(f"collection incomplete: found {len(records)} of {expected_calls} expected scored records")
    _validate_score_support(records)
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(json.dumps({
        "estimated_cost_usd": estimate,
        "collector": {
            "name": "collect_current_model_study.py",
            "schema_version": 1,
            "calls": len(definition["items"]) * EPOCHS_PER_ITEM,
            "input_price_per_million": input_price_per_million,
            "output_price_per_million": output_price_per_million,
            "estimation_method": "UTF-8 bytes / 4 for prompt tokens plus configured maximum completion tokens",
        },
        "provider": provider_label,
        "generation_parameters": {
            "model_id": "claude-sonnet-4-6",
            "max_tokens": max_output_tokens,
            "temperature": None,
            "sampling": "provider-default; this Claude Messages interface does not accept a temperature parameter",
            "epochs_per_item": EPOCHS_PER_ITEM,
        },
        "input_provenance": {"study_definition_sha256": _canonical_hash(definition), "source": definition.get("source", "unspecified")},
        "prompt_manifest": {"study_definition_sha256": _canonical_hash(definition), "raw_prompts_retained_outside_HUD": True},
        "scorer_configuration": {"scorer_sha256": _sha256_bytes(Path(scorer.__code__.co_filename).read_bytes()), "interface": "score(item, completion)"},
        "collection_timestamp": datetime.now(UTC).isoformat(),
        "collection_seed": {
            "study_selection_seed": definition.get("collection_seed", "not-applicable"),
            "provider_sampling_seed": None,
            "note": "the collection does not claim a fixed provider sampling seed; stochastic sampling is recorded through the frozen traces",
        },
    }, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-definition", type=Path, required=True)
    parser.add_argument("--scorer", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    # Ten multiple-choice answers fit comfortably in 64 tokens. A small cap is
    # both sufficient for the strict output protocol and prevents collection
    # spend from being dominated by unused completion allowance.
    parser.add_argument("--max-output-tokens", type=int, default=64)
    parser.add_argument("--input-price-per-million", type=float, required=True)
    parser.add_argument("--output-price-per-million", type=float, required=True)
    parser.add_argument(
        "--temperature", type=float,
        help="Unsupported by the current Claude Messages interface; omit this option.",
    )
    parser.add_argument(
        "--provider", choices=("hud-gateway", "anthropic"), default="hud-gateway",
        help="External collection route; defaults to HUD's Anthropic-compatible inference gateway.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="resume a validated scored-only JSONL checkpoint")
    args = parser.parse_args()
    if (
        args.max_output_tokens <= 0
        or args.input_price_per_million < 0
        or args.output_price_per_million < 0
    ):
        raise SystemExit("prices must be non-negative and max-output-tokens positive")
    if args.temperature is not None:
        raise SystemExit("--temperature is unsupported by the current Claude Messages interface; omit it to use provider-default sampling")
    collect(
        _load_definition(args.study_definition), _load_scorer(args.scorer), output=args.output_jsonl,
        metadata_output=args.metadata_output, max_output_tokens=args.max_output_tokens,
        input_price_per_million=args.input_price_per_million, output_price_per_million=args.output_price_per_million,
        dry_run=args.dry_run, resume=args.resume, provider=args.provider,
    )


if __name__ == "__main__":
    main()
