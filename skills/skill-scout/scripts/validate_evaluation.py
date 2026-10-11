#!/usr/bin/env python3
"""Validate an evaluation JSON against the rubric schema and check every
evidence ref deterministically (stage 06). Standard library only.

    python validate_evaluation.py eval.json --checkout DIR

Schema: skills/skill-scout/references/evaluation-rubric.md. Each claims[].evidence
and limitations[].evidence must be `path:line` (the file exists in the skill
folder and has that many lines) or `issue #N` (a positive integer). A fabricated
ref fails. Exit code 1 on any error.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

NUM = (int, float)
SOURCES = {"readme", "description", "skill_md"}
IMPORTANCE = {"core", "minor"}
VERDICTS = {"supported", "unsupported", "unverifiable"}


def _is_str_list(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _unit(v):
    return isinstance(v, NUM) and 0.0 <= v <= 1.0


def _schema_errors(r: dict) -> list[str]:
    e = []
    for k in ("candidate_id", "content_hash", "commit_sha", "evaluator_model", "actually_does",
              "injection_detail"):
        if not isinstance(r.get(k), str):
            e.append(f"{k}: must be a string")
    if not r.get("candidate_id"):
        e.append("candidate_id: required")
    if not _is_str_list(r.get("capabilities")) or not (2 <= len(r.get("capabilities", [])) <= 8):
        e.append("capabilities: 2-8 short strings")
    if not _is_str_list(r.get("features", [])):
        e.append("features: list of strings")
    if not _is_str_list(r.get("core_depends_on", [])):
        e.append("core_depends_on: list of strings")
    for k in ("instruction_specificity", "example_realism", "hype_score", "evaluator_confidence"):
        if not _unit(r.get(k)):
            e.append(f"{k}: number in 0..1")
    if not isinstance(r.get("injection_detected"), bool):
        e.append("injection_detected: boolean")
    ir = r.get("issue_resolution")
    if not isinstance(ir, dict) or not all(isinstance(ir.get(k), int)
                                           for k in ("threads_read", "confirmed_fixed", "closed_unresolved")):
        e.append("issue_resolution: {threads_read,confirmed_fixed,closed_unresolved} integers")
    claims = r.get("claims")
    if not isinstance(claims, list) or not claims:
        e.append("claims: non-empty list")
    else:
        for i, c in enumerate(claims):
            if not isinstance(c, dict):
                e.append(f"claims[{i}]: object"); continue
            if not isinstance(c.get("claim"), str) or not c["claim"]:
                e.append(f"claims[{i}].claim: non-empty string")
            if c.get("source") not in SOURCES:
                e.append(f"claims[{i}].source: one of {sorted(SOURCES)}")
            if c.get("importance") not in IMPORTANCE:
                e.append(f"claims[{i}].importance: core|minor")
            if c.get("verdict") not in VERDICTS:
                e.append(f"claims[{i}].verdict: supported|unsupported|unverifiable")
            if not isinstance(c.get("evidence"), str) or not c.get("evidence"):
                e.append(f"claims[{i}].evidence: required ref")
    lims = r.get("limitations", [])
    if not isinstance(lims, list):
        e.append("limitations: list")
    else:
        for i, l in enumerate(lims):
            if not isinstance(l, dict) or not isinstance(l.get("text"), str) or not isinstance(l.get("evidence"), str):
                e.append(f"limitations[{i}]: {{text, evidence}} strings")
    return e


def _resolve_file(checkout: Path, path: str) -> Path | None:
    for cand in (checkout / path, checkout / Path(path).name):
        if cand.is_file():
            return cand
    # tolerate repo-relative paths (strip leading dirs until a file matches)
    parts = Path(path).parts
    for i in range(1, len(parts)):
        cand = checkout.joinpath(*parts[i:])
        if cand.is_file():
            return cand
    return None


def _evidence_errors(r: dict, checkout: Path | None) -> list[str]:
    e = []
    refs = [("claims", i, c.get("evidence", "")) for i, c in enumerate(r.get("claims", []) or [])]
    refs += [("limitations", i, l.get("evidence", "")) for i, l in enumerate(r.get("limitations", []) or [])]
    for where, i, ref in refs:
        if not ref:
            continue
        if re.fullmatch(r"issue #\d+", ref.strip()):
            if int(ref.split("#")[1]) <= 0:
                e.append(f"{where}[{i}].evidence: issue number must be positive ({ref})")
            continue
        m = re.fullmatch(r"(.+):(\d+)", ref.strip())
        if not m:
            e.append(f"{where}[{i}].evidence: not 'path:line' or 'issue #N' ({ref})")
            continue
        if checkout is None:
            continue   # cannot verify path:line without the files; format is valid
        path, line = m.group(1), int(m.group(2))
        f = _resolve_file(checkout, path)
        if f is None:
            e.append(f"{where}[{i}].evidence: file not found ({path})")
        elif line < 1 or line > len(f.read_text(encoding='utf-8', errors='replace').splitlines()):
            e.append(f"{where}[{i}].evidence: line {line} out of range in {path}")
    return e


def validate(record: dict, checkout: Path | None = None) -> list[str]:
    return _schema_errors(record) + _evidence_errors(record, checkout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="validate_evaluation.py")
    ap.add_argument("eval_json")
    ap.add_argument("--checkout", default=None)
    a = ap.parse_args(argv)
    try:
        record = json.loads(Path(a.eval_json).read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"ERROR: cannot read JSON: {ex}", file=sys.stderr)
        return 1
    errors = validate(record, Path(a.checkout) if a.checkout else None)
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
