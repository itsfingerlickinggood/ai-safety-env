"""Build a leak-resistant, agent-facing paper extraction from the pinned PDF.

The source PDF is deliberately supplied outside the HUD Docker context.  This
script creates deterministic Markdown plus a provenance manifest for the
phase-one workspace.  It conservatively removes every empirical-results page
whose content cannot be separated reliably from a result-bearing figure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader


TITLE = "Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"\noptstop\n", "\n", text)
    return text.strip()


def _redact_page(number: int, text: str) -> tuple[str, str | None]:
    """Return safe text and a reason when a page is intentionally withheld."""
    if number == 1:
        match = re.search(r"\b1 Introduction\b", text)
        if match:
            return (
                f"# {TITLE}\n\n"
                "## Abstract\n\n[RESULTS REDACTED: abstract outcome claims]\n\n"
                + text[match.start() :],
                "abstract outcome claims",
            )
    if number == 5:
        match = re.search(r"\b3\.1 Stopping Efficiency", text)
        if match:
            return (
                text[: match.start()].rstrip()
                + "\n\n## 3.1 Stopping Efficiency and Score Fidelity\n\n"
                "[RESULTS REDACTED: empirical metrics, comparisons, and conclusions]\n",
                "main empirical results",
            )
    if 6 <= number <= 8:
        return (
            "[RESULTS REDACTED: result-bearing main-text analysis, figures, and conclusions]",
            "main empirical results and conclusions",
        )
    # Appendix B begins on source page 20. Its opening page contains outcome
    # claims in prose before the first result table, so redacting from page 21
    # leaks answer-bearing validation evidence.
    if 20 <= number <= 32:
        return (
            "[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]",
            "empirical appendix",
        )
    return text, None


def build(source: Path, output: Path, provenance: Path) -> None:
    reader = PdfReader(source)
    sections = [
        "<!-- Generated from the pinned source PDF. Do not edit manually; rerun this script. -->",
        "# Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations",
        "",
        "This is a source-derived agent-facing extraction for the Core Reproduction v1 task. "
        "The main methods, experimental setup, formal Appendix A material, limitations, and references are retained. "
        "The empirical Appendix B is withheld as a unit because its pages interleave result-bearing validation with prose. "
        "Answer-bearing empirical results are replaced with explicit placeholders.",
    ]
    redactions: list[dict[str, object]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = _clean(page.extract_text() or "")
        safe, reason = _redact_page(index, text)
        sections.extend(["", f"<!-- Source page {index} -->", safe])
        if reason:
            redactions.append({"page": index, "reason": reason})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(sections).strip() + "\n", encoding="utf-8")
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "title": TITLE,
                "source": "arXiv:2608.14425 / pinned UKGovernmentBEIS optstop paper PDF",
                "source_pdf_sha256": _sha256(source),
                "source_pages": len(reader.pages),
                "redaction_policy": "Remove all result-bearing claims, tables, figures, captions, conclusions, and empirical appendix material.",
                "redactions": redactions,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output, args.provenance)


if __name__ == "__main__":
    main()
