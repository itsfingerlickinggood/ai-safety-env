# External current-model trace collection

Core v1 cannot use the authors' original historical traces: they are not in
the pinned upstream release. It therefore requires a separately collected,
current-model study. This collection is outside HUD and must be reviewed before
any API calls.

For the supported first study, create these files with
[`MMLU_CORE_V1_PROTOCOL.md`](MMLU_CORE_V1_PROTOCOL.md). Prepare both private
files outside this repository:

- `study_definition.json`, matching `study_definition.schema.json`, with 180
  pinned and provenance-licensed MMLU-derived items: 20 for each 3x3 cell.
  Each item has a prompt, cell metadata, stable item ID, and private answer
  keys. The generated `low`/`mid`/`high` labels are challenge strata, not
  pre-collection performance claims.
- `scorer.py`, defining `score(item: dict, completion: str) -> float`. It must
  use benchmark ground truth or a pinned evaluator, not a model self-rating.
  Binary and continuous scores must be in `[0, 1]`; ordinal scores must be an
  integer in `[0, 10]`.

First perform the no-call budget/schema check. Supply current provider prices
in USD per million tokens; these parameters are recorded in the generated
metadata.

```bash
uv run python scripts/collect_current_model_study.py \
  --study-definition /secure/study_definition.json \
  --scorer /secure/scorer.py \
  --output-jsonl /secure/scored_traces.jsonl \
  --metadata-output /secure/collection_metadata.json \
  --input-price-per-million INPUT_PRICE \
  --output-price-per-million OUTPUT_PRICE \
  --max-output-tokens 64 \
  --dry-run
```

Only if the estimate is at most $50, repeat without `--dry-run` in a shell
where `HUD_API_KEY` is set. The default collection route is HUD's
Anthropic-compatible inference gateway; the credential is used only by this
external collector and is never written to the repository or deployed image.
To deliberately use a direct Anthropic account instead, pass `--provider
anthropic` and set `ANTHROPIC_API_KEY`. The collector stores scores and hashes
only; it does not persist raw model completions or credentials. Then package
and freeze the data as documented in the repository README.

The collector checkpoints each normalized score after a successful API call;
it never writes raw completions. If an API/network interruption occurs, rerun
the same command with `--resume` and exactly the same definition, scorer, and
output paths. It validates every pre-existing record against the definition
and refuses duplicates or mismatches. Do not delete a checkpoint merely to
restart it: doing so can repeat already billed calls.

Do not substitute synthetic prompts, self-scored model answers, or a claimed
cost number for the pinned inputs, independent scorer, and computed estimate.
The four epochs use the provider's default sampling behavior: the current
Claude Messages interface does not accept a caller-selected temperature. The
definition's fixed seed selects benchmark items; it is not misrepresented as
a provider sampling seed.
