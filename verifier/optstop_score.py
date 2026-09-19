"""Deterministic grader for the frozen optstop Core Reproduction v1 bundle.

All answer-bearing reference artifacts live in ``verifier/private_optstop``.
That directory is intentionally gitignored, copied into the Docker image, and
made unreadable to the agent by the image's verifier permissions.
"""

from __future__ import annotations

import contextlib
import json
import hashlib
import math
import os
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from verifier.output_validation import valid_ablations, valid_forecast, valid_plan, valid_report, valid_reproduction_results


REPO = Path(__file__).resolve().parents[1]
PRIVATE = Path(__file__).resolve().parent / "private_optstop"
ANALYSIS_MANIFEST = REPO / "paper_reproduction" / "release" / "analysis_manifest.json"
WEIGHTS = {
    "forecast": 0.10,
    "plan_manifest": 0.15,
    "numerical_reproduction": 0.35,
    "ablations": 0.15,
    "hidden_robustness": 0.15,
    "report_interpretation": 0.10,
}
MAX_FILE_BYTES = 8 * 1024 * 1024


def _regular_text(path: Path, limit: int = MAX_FILE_BYTES) -> str:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError(f"invalid workspace file: {path.name}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        return stream.read(limit + 1)


def _json(path: Path) -> Any:
    return json.loads(_regular_text(path))


def _load_bundle() -> dict[str, Any]:
    bundle = _json(PRIVATE / "reference_bundle.json")
    if bundle.get("status") != "complete" or bundle.get("schema_version") != 1:
        raise RuntimeError("private optstop reference bundle is absent or incomplete")
    return bundle


def _manifest_ids() -> set[str]:
    return {str(entry["id"]) for entry in _json(ANALYSIS_MANIFEST)["required_analyses"]}


def _bounded(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("probability must be finite and in [0, 1]")
    return number


def _forecast_score(root: Path, bundle: dict[str, Any]) -> float:
    try:
        forecast = _json(root / "forecast.json")
        if not valid_forecast(forecast):
            return 0.0
        binary = {str(item["id"]): _bounded(item["probability"]) for item in forecast["binary"]}
        continuous = {
            str(item["id"]): (float(item["mean"]), float(item["std"]))
            for item in forecast["continuous"]
        }
        if set(binary) != set(bundle["forecast_outcomes"]["binary"]) or set(continuous) != set(bundle["forecast_outcomes"]["continuous"]):
            return 0.0
        brier = [(binary[key] - float(value)) ** 2 for key, value in bundle["forecast_outcomes"]["binary"].items()]
        crps_scores = []
        for key, target in bundle["forecast_outcomes"]["continuous"].items():
            mean, std = continuous[key]
            if not math.isfinite(mean) or not math.isfinite(std) or std <= 0:
                return 0.0
            z = (float(target) - mean) / std
            normal_cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
            normal_pdf = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
            # CRPS is a proper score for a Normal predictive distribution.
            crps_scores.append(std * (z * (2.0 * normal_cdf - 1.0) + 2.0 * normal_pdf - 1.0 / math.sqrt(math.pi)))
        binary_score = 1.0 - float(np.mean(brier)) if brier else 0.0
        # This fixed scale maps a proper loss to a bounded reward without
        # clipping. A worse calibrated forecast always lowers this component.
        continuous_score = math.exp(-float(np.mean(crps_scores)) / 0.25) if crps_scores else 0.0
        return 0.6 * binary_score + 0.4 * continuous_score
    except Exception:
        return 0.0


def _plan_score(root: Path, required_ids: set[str]) -> float:
    try:
        plan = _json(root / "experiment_plan.json")
        if not valid_plan(plan):
            return 0.0
        text = json.dumps(plan).lower()
        registered = set(map(str, plan.get("analysis_manifest", [])))
        checks = [
            len(str(plan.get("research_question", ""))) >= 40,
            len(plan.get("hypotheses", [])) >= 3,
            len(plan.get("controls", [])) >= 3,
            len(plan.get("ablations", [])) >= 3,
            len(plan.get("falsification_criteria", [])) >= 2,
            "seed" in text and "rope" in text,
            "leak" in text and "forecast" in text,
            registered == required_ids,
        ]
        return float(np.mean(checks))
    except Exception:
        return 0.0


def _numerical_score(root: Path, bundle: dict[str, Any]) -> float:
    try:
        result = _json(root / "reproduction_results.json")
        if not valid_reproduction_results(result):
            return 0.0
        expected = bundle["public_reference"]["cells"]
        tolerances = bundle["tolerances"]
        checks: list[bool] = []
        for cell_id, target in expected.items():
            actual = result["cells"][cell_id]
            for metric in ("efficiency", "full_mean", "retained_mean", "absolute_difference"):
                checks.append(abs(float(actual[metric]) - float(target[metric])) <= float(tolerances["cells"][cell_id][metric]))
            checks.append(int(actual["paired_n"]) == int(target["paired_n"]))
            checks.append(abs(float(actual["paired_mean_difference"]) - float(target["paired_mean_difference"])) <= float(tolerances["cells"][cell_id]["paired_mean_difference"]))
            checks.append(abs(float(actual["paired_hdi_94"][0]) - float(target["paired_hdi_94"][0])) <= float(tolerances["cells"][cell_id]["paired_hdi_lower"]))
            checks.append(abs(float(actual["paired_hdi_94"][1]) - float(target["paired_hdi_94"][1])) <= float(tolerances["cells"][cell_id]["paired_hdi_upper"]))
            checks.append(float(actual["rope"]) == float(target["rope"]))
            checks.append(actual["equivalence_decision"] == target["equivalence_decision"])
            checks.append((actual.get("error") is None) == (target.get("error") is None))
        for metric in ("mean_efficiency", "mean_absolute_difference"):
            checks.append(abs(float(result[metric]) - float(bundle["public_reference"][metric])) <= float(tolerances["aggregate"][metric]))
        checks.append(result["overall_equivalence_decision"] == bundle["public_reference"]["overall_equivalence_decision"])
        return float(np.mean(checks))
    except Exception:
        return 0.0


def _ablation_score(root: Path, required_ids: set[str], bundle: dict[str, Any]) -> float:
    required = {identifier for identifier in required_ids if identifier not in bundle["public_reference"]["cells"]}
    try:
        payload = _json(root / "ablations.json")
        if not valid_ablations(payload):
            return 0.0
        entries = {str(item["id"]): item for item in payload["ablations"]}
        if not required.issubset(entries):
            return 0.0
        checks = []
        for identifier in required:
            entry = entries[identifier]
            reference = bundle["ablation_reference"][identifier]
            checks.extend(
                [
                    str(entry.get("changed_parameter", "")).strip() == str(reference["changed_parameter"]),
                    bool(str(entry.get("interpretation", "")).strip()),
                    math.isfinite(float(entry["effect_size"])),
                    math.isfinite(float(entry["uncertainty"])) and float(entry["uncertainty"]) >= 0.0,
                    abs(float(entry["effect_size"]) - float(reference["effect_size"])) <= float(reference["tolerance"]),
                    abs(float(entry["uncertainty"]) - float(reference["uncertainty"])) <= float(reference["tolerance"]),
                    str(entry.get("outcome", "")) == str(reference["outcome"]),
                ]
            )
        return float(np.mean(checks))
    except Exception:
        return 0.0


def _copy_regular_tree(source: Path, destination: Path) -> None:
    destination.mkdir(mode=0o755)
    for current, dirnames, filenames in os.walk(source, followlinks=False):
        current_path = Path(current)
        target_dir = destination / current_path.relative_to(source)
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in list(dirnames):
            candidate = current_path / name
            if candidate.is_symlink() or not candidate.is_dir():
                raise ValueError(f"agent workspace contains non-directory: {candidate.relative_to(source)}")
        for name in filenames:
            candidate = current_path / name
            info = candidate.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                raise ValueError(f"agent workspace contains invalid file: {candidate.relative_to(source)}")
            target = target_dir / name
            shutil.copyfile(candidate, target)
            os.chmod(target, 0o555 if name == "submission.py" else 0o444)
    for current, _, _ in os.walk(destination):
        os.chmod(current, 0o555)


def _run_submission(root: Path, inputs: Path, output: Path) -> tuple[int, str]:
    launcher = os.environ.get("HUD_SANDBOX_EXEC")
    command = [sys.executable, str(root / "submission.py"), "--input-dir", str(inputs), "--output", str(output)]
    if launcher and os.environ.get("HUD_FORCE_UNSANDBOXED_GRADER") != "1":
        command = [launcher, "--uid", os.environ.get("HUD_AGENT_UID", "65532"), "--gid", os.environ.get("HUD_AGENT_GID", "65532"), *command]
    vendor = root / "phase_two" / "vendor"
    if not vendor.is_dir():
        vendor = root / "vendor"
    process = subprocess.Popen(
        command,
        cwd=root,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": str(vendor)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        _, stderr = process.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        # The submission may fork a child before timing out. It runs in a
        # dedicated session, so kill the full group rather than leaving an
        # agent-owned descendant running alongside later grades.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        _, stderr = process.communicate()
        return 124, f"submission timed out after 900 seconds; {stderr[-1800:]}"
    return process.returncode, stderr[-2000:]


def _hidden_score(root: Path, bundle: dict[str, Any]) -> tuple[float, str | None]:
    # A hidden suite must be stable for a task instance. SystemRandom makes
    # reward change on regrade, which is unacceptable for an RL benchmark.
    instance = os.environ.get("HUD_TASK_INSTANCE_ID") or os.environ.get("HUD_EVAL_SEED") or "default"
    material = f"{bundle['hidden_selection_salt']}:{instance}".encode()
    variants_by_id = {str(variant["id"]): variant for variant in bundle["hidden_variants"]}
    scoring_ids = [str(value) for value in bundle.get("scoring_hidden_variant_ids", variants_by_id)]
    if not scoring_ids or any(identifier not in variants_by_id for identifier in scoring_ids):
        return 0.0, "hidden scoring variant selection is invalid"
    index = int.from_bytes(hashlib.sha256(material).digest()[:8], "big") % len(scoring_ids)
    chosen = variants_by_id[scoring_ids[index]]
    inputs = PRIVATE / "hidden" / str(chosen["id"])
    expected = chosen["reference"]
    try:
        with tempfile.TemporaryDirectory(prefix="optstop-hidden-") as raw:
            temp = Path(raw)
            # TemporaryDirectory is mode 0700 by default. The unprivileged
            # runner must be able to traverse this parent, but it must not be
            # able to enumerate sibling paths or write anywhere except output.
            os.chmod(temp, 0o711)
            submission = temp / "submission"
            _copy_regular_tree(root, submission)
            staged_inputs = temp / "inputs"
            # The root-only verifier data cannot be passed to uid 65532
            # directly. Stage only the selected score-trace matrix as
            # root-owned, read-only files for this one subprocess. It is never
            # copied into the agent workspace or made visible before grading.
            _copy_regular_tree(inputs, staged_inputs)
            output_dir = temp / "output"
            output_dir.mkdir(mode=0o700)
            if os.geteuid() == 0 and os.environ.get("HUD_FORCE_UNSANDBOXED_GRADER") != "1":
                os.chown(output_dir, int(os.environ.get("HUD_AGENT_UID", "65532")), int(os.environ.get("HUD_AGENT_GID", "65532")))
            output = output_dir / "result.json"
            return_code, stderr = _run_submission(submission, staged_inputs, output)
            if return_code or not output.exists():
                return 0.0, f"hidden submission failed: rc={return_code}; {stderr}"
            actual = _json(output)
            if not valid_reproduction_results(actual):
                return 0.0, "hidden submission did not emit the required reproduction-results schema"
            checks = []
            for cell_id, target in expected["cells"].items():
                got = actual["cells"][cell_id]
                for metric in ("efficiency", "full_mean", "retained_mean", "absolute_difference"):
                    checks.append(abs(float(got[metric]) - float(target[metric])) <= float(chosen["tolerances"]["cells"][cell_id][metric]))
                checks.append(int(got["paired_n"]) == int(target["paired_n"]))
                checks.append(abs(float(got["paired_mean_difference"]) - float(target["paired_mean_difference"])) <= float(chosen["tolerances"]["cells"][cell_id]["paired_mean_difference"]))
                checks.append(abs(float(got["paired_hdi_94"][0]) - float(target["paired_hdi_94"][0])) <= float(chosen["tolerances"]["cells"][cell_id]["paired_hdi_lower"]))
                checks.append(abs(float(got["paired_hdi_94"][1]) - float(target["paired_hdi_94"][1])) <= float(chosen["tolerances"]["cells"][cell_id]["paired_hdi_upper"]))
                checks.append(float(got["rope"]) == float(target["rope"]))
                checks.append(got["equivalence_decision"] == target["equivalence_decision"])
            return float(np.mean(checks)), str(chosen["id"])
    except Exception as exc:
        return 0.0, f"hidden submission invalid: {exc}"


def _report_context(root: Path, bundle: dict[str, Any]) -> str:
    report = _regular_text(root / "final_report.md", limit=2 * 1024 * 1024)
    if not valid_report(report):
        raise ValueError("final report does not satisfy the required scientific-report structure")
    return json.dumps(
        {
            "agent_report": report,
            "agent_results": _json(root / "reproduction_results.json"),
            "agent_ablations": _json(root / "ablations.json"),
            "golden_evidence": bundle["judge_evidence"],
        },
        ensure_ascii=False,
    )


def score_optstop_workspace(root: Path, *, forecast_locked: bool, plan_locked: bool) -> dict[str, Any]:
    root = Path(root)
    bundle = _load_bundle()
    required_ids = _manifest_ids()
    required_files = {"forecast.json", "experiment_plan.json", "reproduction_results.json", "ablations.json", "final_report.md", "submission.py"}
    notes: list[str] = []
    if not forecast_locked:
        notes.append("forecast lock failed")
    if not plan_locked:
        notes.append("experiment plan lock failed")
    interface = float(all((root / name).is_file() for name in required_files))
    forecast = _forecast_score(root, bundle) if forecast_locked else 0.0
    plan = _plan_score(root, required_ids) if plan_locked else 0.0
    numerical = _numerical_score(root, bundle)
    ablations = _ablation_score(root, required_ids, bundle)
    hidden, hidden_note = _hidden_score(root, bundle)
    if hidden_note:
        notes.append(hidden_note)
    report_context = ""
    try:
        report_context = _report_context(root, bundle)
    except Exception as exc:
        notes.append(f"report unavailable for judge: {exc}")
    components = {
        "forecast": forecast,
        "plan_manifest": min(interface, plan),
        "numerical_reproduction": min(interface, numerical),
        "ablations": min(interface, ablations),
        "hidden_robustness": min(interface, hidden),
        "report_interpretation": 0.0,
    }
    deterministic = sum(WEIGHTS[key] * value for key, value in components.items())
    if numerical < 0.5 or ablations < 0.5:
        deterministic = min(deterministic, 0.50)
        notes.append("reward capped because required numerical analyses or ablations are incomplete")
    return {
        "deterministic_reward": float(deterministic),
        "components": components,
        "weights": WEIGHTS,
        "notes": notes,
        "report_context": report_context,
    }
