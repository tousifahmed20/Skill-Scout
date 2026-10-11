"""Provisional credibility score from evaluation fields (stage 06).

ponytail: stage 08 (ranking) owns the canonical formula; this exists so stage 06
can self-test Done-when #1 (good ranks above hype). It is monotone in the fields
that separate substance from hype and is deliberately simple — if stage 08 tunes
weights, this moves there.
"""
from __future__ import annotations


def _num(v, default=0.0):
    return float(v) if isinstance(v, (int, float)) else default


def credibility(rec: dict) -> float:
    """0..1. Higher = claims are backed by substance."""
    if rec.get("injection_detected"):
        return 0.0                                   # manipulative skill: not recommendable
    claims = rec.get("claims") or []
    core = [c for c in claims if c.get("importance") == "core"]
    core_unsupported = sum(1 for c in core if c.get("verdict") == "unsupported")
    core_supported = sum(1 for c in core if c.get("verdict") == "supported")
    core_total = len(core) or 1

    hype = _num(rec.get("hype_score"))
    spec = _num(rec.get("instruction_specificity"))
    realism = _num(rec.get("example_realism"))
    ir = rec.get("issue_resolution") or {}
    fixed = int(ir.get("confirmed_fixed", 0) or 0)
    unresolved = int(ir.get("closed_unresolved", 0) or 0)
    resolution = 0.0
    if fixed + unresolved:
        resolution = (fixed - unresolved) / (fixed + unresolved)   # -1..1

    score = (0.45 * (1 - hype)
             + 0.20 * (core_supported / core_total)
             + 0.15 * spec
             + 0.15 * realism
             + 0.05 * (resolution + 1) / 2)
    score -= 0.25 * (core_unsupported / core_total)                # unbacked core claims hurt most
    return round(max(0.0, min(1.0, score)), 4)
