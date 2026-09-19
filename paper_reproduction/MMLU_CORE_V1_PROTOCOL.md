# MMLU current-model study protocol

This is the concrete external input-generation protocol for the first Core v1
study. It is a bounded independent study that uses a pinned public
[`cais/mmlu`](https://huggingface.co/datasets/cais/mmlu) snapshot at revision
`c30699e8356da336a370243923dbaf21066bb9fe` (MIT license). It is not a replay
of the paper authors' original benchmark calls or their historical traces.

The expected SHA-256 for `all/test-00000-of-00001.parquet` is
`74a41822ce7d3def56e1682f958469c04642a5336a5ce912fa375fdb90fb25d7`.
The builder rejects a file with any other hash.

Download the `all/test` parquet snapshot to a secure directory outside this
repository. Verify its SHA-256 after download, then generate the external
definition and deterministic scorer:

```bash
hf download cais/mmlu all/test-00000-of-00001.parquet \
  --revision c30699e8356da336a370243923dbaf21066bb9fe \
  --local-dir /secure/mmlu-snapshot

uv run --with pyarrow==17.0.0 python scripts/build_mmlu_core_v1_study.py \
  --mmlu-test-parquet /secure/mmlu-snapshot/all/test-00000-of-00001.parquet \
  --output-definition /secure/external_study/study_definition.json \
  --output-scorer /secure/external_study/scorer.py
```

The generated package has 20 items in every core cell. Binary items contain
one question. Ordinal and continuous items contain ten independently scored
multiple-choice questions: ordinal score is the integer number correct
(`0..10`), while continuous score is the fraction correct (`0..1`). The
scorer accepts only a strict `<answers>A,B,...</answers>` response, so it does
not rely on self-reported quality or an LLM judge.

`low`, `mid`, and `high` are pre-registered challenge strata selected from
documented MMLU subject pools. They are *not* claimed to be observed low,
mid, and high model-performance groups before collection. The final report
must state whether the collected data support that intended ordering.

MMLU is public and may have appeared in model training data. Core v1 therefore
uses it to study the operational behavior of the stopping procedure on a
provenance-controlled score matrix, not to make a contamination-free claim
about frontier-model capability or real-world research performance. This
limitation is required in the final report.

The retained/full comparison is a paired, item-level Student-t posterior
approximation with a 94% interval and pre-registered ROPE. It is a bounded,
deterministic Core v1 analysis, not a substitute for the paper's larger
hierarchical appendix analyses.

Keep the generated definition, answer keys, raw provider responses, and API
credentials outside the repository and outside the HUD workspace. Only the
validated score traces and hashes are packaged for the agent-facing study.
