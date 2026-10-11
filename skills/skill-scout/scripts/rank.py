#!/usr/bin/env python3
"""Fit-and-rank (stage 08). Standard library only. One implementation for the
shipped skill and the server.

    python rank.py task-template
    python rank.py retrieve --task task.json      # pipeline steps 1-4 -> shortlist.json
    python rank.py rank --task task.json --fits fits.json   # steps 5-12 -> ranked.json

Every number comes from references/ranking-config.json (scoring.md / engines.md).
Steps: retrieve -> exclude -> shortlist -> harness/constraints (here), the model
writes fits (step 5, steps/04-fit-rank.md), then floor/score/order/gem/flags here.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import store as store_mod

REF = Path(__file__).resolve().parent.parent / "references"
CFG = json.loads((REF / "ranking-config.json").read_text(encoding="utf-8"))
PROFILES = json.loads((REF / "harness-profiles.json").read_text(encoding="utf-8"))
PROFILE = {h["id"]: h for h in PROFILES["harnesses"]}
DEFAULT_K = 30

TASK_TEMPLATE = {
    "task_text": "the user's sentence", "task_label": "<= 8 words",
    "capabilities": ["2-6 verb phrases"],
    "search_terms": ["8-15 keywords and synonyms for the task"],
    "constraints": {"os": None, "free_only": False, "offline": False, "language": None},
    "host_harness": "<harness id or unknown>",
}


# ---- helpers -----------------------------------------------------------------
def _num(v, d=0.0):
    return float(v) if isinstance(v, (int, float)) else d


def _pct(value, peers) -> float:
    """Fraction of peers (incl. self) with value <= this. Singleton -> 0.5."""
    vals = [v for v in peers if v is not None]
    if len(vals) <= 1:
        return 0.5
    return sum(1 for v in vals if v <= value) / len(vals)


def credibility(ev: dict | None) -> float:
    c = CFG["credibility"]
    if not ev:
        return 0.0
    cw, mw = c["core_weight"], c["minor_weight"]
    num = den = 0.0
    unsupported_core = 0
    for cl in ev.get("claims", []):
        if cl.get("verdict") == "unverifiable":
            continue
        w = cw if cl.get("importance") == "core" else mw
        den += w
        if cl.get("verdict") == "supported":
            num += w
        elif cl.get("verdict") == "unsupported" and cl.get("importance") == "core":
            unsupported_core += 1
    if den == 0:
        return c["neutral_if_no_verifiable_claims"]
    score = num / den - c["penalty_per_unsupported_core"] * unsupported_core
    return max(0.0, min(1.0, score))


def unsupported_core_count(ev: dict | None) -> int:
    return sum(1 for cl in (ev.get("claims", []) if ev else [])
              if cl.get("importance") == "core" and cl.get("verdict") == "unsupported")


def effective_level(bundle: dict, host: str) -> tuple[str, list[str]]:
    compat = bundle.get("compatibility") or {}
    harness = (compat.get("harness") or {}).get(host) or {}
    level = harness.get("level", "unknown")
    reasons = list(harness.get("reasons", []))
    ev = bundle.get("evaluation")
    sup = (PROFILE.get(host) or {}).get("supports", {})
    for feat in (ev.get("core_depends_on", []) if ev else []):
        ok = sup.get("mcp", False) if feat.startswith("mcp:") else sup.get(feat, False)
        if not ok:
            level = "incompatible"
            reasons.append(f"core depends on '{feat}', unsupported by {host}")
    return level, reasons


def _constraint_break(bundle: dict, cons: dict) -> str | None:
    req = (bundle.get("compatibility") or {}).get("requirements") or {}
    if cons.get("os") and req.get("os") and "any" not in req["os"] and cons["os"] not in req["os"]:
        return f"needs OS {req['os']}, user is on {cons['os']}"
    if cons.get("offline") and req.get("network"):
        return "needs network, user asked for offline"
    if cons.get("free_only") and any(s.get("paid") for s in req.get("services", [])):
        return "needs a paid service, user asked for free only"
    return None


# ---- retrieve (steps 1-4) ----------------------------------------------------
def retrieve(task: dict, store) -> dict:
    host = task.get("host_harness", "unknown")
    terms = " ".join(task.get("search_terms", [])) + " " + " ".join(task.get("capabilities", []))
    hits = store.search(terms, DEFAULT_K)

    cand, excluded = [], []
    for cid, rel in hits:
        try:
            b = store.bundle(cid)
        except KeyError:
            continue
        if b["candidate"].get("status") != "active":
            continue
        ev = b["evaluation"]
        if ev and ev.get("injection_detected"):
            continue
        ver = b["verification"]
        if ver and ver.get("verdict") in CFG["floor"]["drop_verdicts"]:
            continue
        cand.append((cid, rel, b))

    # pre-score = relevance x mean of available normalized Hard/Medium health signals
    sig_keys = ["substantive_commits_90d", "independent_contributors", "independent_issue_reports", "forks"]
    ranges = {}
    for k in sig_keys:
        xs = [_num((c[2]["health"] or {}).get(k)) for c in cand]
        ranges[k] = (min(xs), max(xs)) if xs else (0, 0)

    def prescore(b, rel):
        h = b["health"] or {}
        norms = []
        for k in sig_keys:
            lo, hi = ranges[k]
            if hi > lo:
                norms.append((_num(h.get(k)) - lo) / (hi - lo))
        return rel * (sum(norms) / len(norms) if norms else 0.5)

    new_days = 14  # CLAUDE.md new-skill window
    def is_new(b):
        fs = (b["candidate"] or {}).get("first_seen")
        return bool(fs) and _days_ago(fs) <= new_days

    scored = sorted(cand, key=lambda c: -prescore(c[2], c[1]))
    top = scored[:CFG["retrieval"]["evaluate_top"]]
    gems = [c for c in scored if is_new(c[2]) and c not in top][:CFG["retrieval"]["gem_reserve"]]
    shortlist = top + gems

    to_evaluate = [c[0] for c in shortlist if c[2]["evaluation_freshness"] in ("missing", "stale")]
    to_evaluate = to_evaluate[:CFG["retrieval"]["max_evaluations_per_query"]]

    set_aside, keep = [], []
    cons = task.get("constraints", {}) or {}
    for cid, rel, b in shortlist:
        lvl, reasons = effective_level(b, host) if host != "unknown" else ("unknown", [])
        broke = _constraint_break(b, cons)
        if host != "unknown" and lvl == "incompatible":
            set_aside.append({"candidate_id": cid, "skill_name": b["candidate"].get("skill_name", ""),
                              "reason": (reasons[-1] if reasons else "incompatible with host")})
        elif broke:
            set_aside.append({"candidate_id": cid, "skill_name": b["candidate"].get("skill_name", ""), "reason": broke})
        else:
            keep.append({"candidate_id": cid, "relevance": rel, "effective_level": lvl, "level_reasons": reasons})
    return {"task": task, "shortlist": keep, "to_evaluate": to_evaluate,
            "set_aside": set_aside[:1], **_harness_meta(host)}


def _harness_meta(host: str) -> dict:
    disp = list(PROFILES["default_display"])
    if host != "unknown" and host not in disp:
        disp.append(host)
    va = host != "unknown" and bool((PROFILE.get(host) or {}).get("verification_runner")) \
        and "verification_runner" not in (PROFILE.get(host) or {}).get("unverified", [])
    return {"display_harnesses": disp, "harness_names": {h: PROFILE[h]["name"] for h in disp if h in PROFILE},
            "verification_available": va}


def _days_ago(iso: str) -> float:
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return 1e9
    if not d.tzinfo:
        d = d.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - d).days


# ---- rank (steps 5-12) -------------------------------------------------------
def _signals(b: dict, groups: dict, cid_cluster: dict, cid: str):
    """Raw-value map; percentile signals resolved against same-cluster peers."""
    h, ev, ver = b["health"] or {}, b["evaluation"] or {}, b["verification"]
    flags = h.get("flags") or []
    cl = cid_cluster.get(cid)

    def pct(key, raw):
        peers = groups.get((cl, key), [raw])
        return _pct(raw, peers)

    s = {}
    s["claims_evidence"] = credibility(ev)
    s["example_realism"] = _num(ev.get("example_realism"))
    s["instruction_specificity"] = _num(ev.get("instruction_specificity"))
    sc = _num(h.get("substantive_commits_90d"))
    s["substantive_commits"] = pct("substantive_commits", sc) * (0.5 if "commit_padding" in flags else 1.0)
    s["contributor_independence"] = pct("contributor_independence", _num(h.get("independent_contributors")))
    # independent_reports = 0.5*pct(usage) + 0.5*resolution
    usage = _num(h.get("independent_issue_reports")) + _num((b["outcome_summary"] or {}).get("yes"))
    fixed = _num((ev.get("issue_resolution") or {}).get("confirmed_fixed")) + _num(h.get("linked_fix_closures"))
    unresolved = _num((ev.get("issue_resolution") or {}).get("closed_unresolved"))
    resolution = fixed / (fixed + unresolved) if (fixed + unresolved) else 0.5
    s["independent_reports"] = 0.5 * pct("independent_reports", usage) + 0.5 * resolution
    # behavioral_delta only when verification present
    if ver and isinstance(ver.get("delta"), (int, float)):
        s["behavioral_delta"] = pct("behavioral_delta", ver["delta"])
    # soft
    repo_factor = CFG["repo_scope_factor"]
    scope = (h.get("scope") or {})
    if "star_burst" in flags:
        s["star_velocity_quality"] = 0.0
    elif h.get("stargazer_quality") is not None:
        sv = _num(h.get("star_velocity_7d")) * _num(h.get("stargazer_quality"))
        s["star_velocity_quality"] = pct("star_velocity_quality", sv) * (repo_factor if scope.get("stars") == "repo" else 1.0)
    if h.get("installs") is not None:
        s["installs"] = pct("installs", _num(h.get("installs"))) * (repo_factor if scope.get("installs") == "repo" else 1.0)
    frl = []
    frl.append(pct("forks", _num(h.get("forks"))))
    frl.append(1.0 if _num(h.get("releases")) > 0 else 0.0)
    frl.append(1.0 if h.get("license") else 0.0)
    s["forks_releases_license"] = sum(frl) / len(frl)
    return s


def _points_for(present: set) -> dict:
    """points[signal] with redistribution: no behavioral_delta -> its points to the
    other Hard signals; a missing Soft -> its points to the other Soft signals."""
    p = {}
    for tier in ("hard", "medium", "soft"):
        p.update(CFG["points"][tier])
    hard = CFG["points"]["hard"]
    if "behavioral_delta" not in present:
        move = hard["behavioral_delta"]
        others = [k for k in hard if k != "behavioral_delta"]
        tot = sum(hard[k] for k in others)
        for k in others:
            p[k] += move * (hard[k] / tot) if tot else 0
        p["behavioral_delta"] = 0
    soft = CFG["points"]["soft"]
    missing_soft = [k for k in soft if k not in present]
    kept_soft = [k for k in soft if k in present]
    if missing_soft and kept_soft:
        move = sum(soft[k] for k in missing_soft)
        tot = sum(soft[k] for k in kept_soft)
        for k in kept_soft:
            p[k] += move * (soft[k] / tot)
        for k in missing_soft:
            p[k] = 0
    return p


def gem_score(b: dict) -> float:
    g = CFG["gem"]["points"]
    h, ev = b["health"] or {}, b["evaluation"] or {}
    files = (b["candidate"] or {}).get("files") or "{}"
    try:
        fobj = json.loads(files) if isinstance(files, str) else files
    except ValueError:
        fobj = {}
    structural = (1.0 if any(fobj.get(k) for k in ("scripts", "references")) else 0.0) * _num(ev.get("example_realism"))
    s = {"instruction_specificity": _num(ev.get("instruction_specificity")),
         "claims_to_substance": 1 - _num(ev.get("hype_score")),
         "structural_seriousness": structural,
         "author_track_record": _num(h.get("author_track_record")),
         "early_organic_traction": _num(h.get("early_organic_traction"))}
    total = sum(g.values())
    return sum(g[k] * s[k] for k in g) / total if total else 0.0


def rank(task: dict, fits: dict, store) -> dict:
    host = task.get("host_harness", "unknown")
    short = retrieve(task, store)
    kept = {c["candidate_id"]: c for c in short["shortlist"]}

    # gather bundles + fits for shortlisted, evaluated candidates
    rows, not_evaluated = [], 0
    for cid, meta in kept.items():
        b = store.bundle(cid)
        if not b["evaluation"]:
            not_evaluated += 1
            continue
        fit = fits.get(cid)
        if not fit or fit.get("fit") == "none":
            if not fit:
                not_evaluated += 1
            continue
        if credibility(b["evaluation"]) < CFG["floor"]["min_credibility"]:
            continue
        if unsupported_core_count(b["evaluation"]) > CFG["floor"]["max_unsupported_core"]:
            continue
        rows.append({"cid": cid, "bundle": b, "fit": fit.get("fit"), "missing": fit.get("missing", []),
                     "level": meta["effective_level"]})

    # percentile groups (per primary cluster, per signal)
    cid_cluster = {r["cid"]: r["bundle"].get("primary_cluster") for r in rows}
    raw = {}
    for r in rows:
        h, ev, ver = r["bundle"]["health"] or {}, r["bundle"]["evaluation"] or {}, r["bundle"]["verification"]
        cl = cid_cluster[r["cid"]]
        add = lambda key, v: raw.setdefault((cl, key), []).append(v)
        add("substantive_commits", _num(h.get("substantive_commits_90d")))
        add("contributor_independence", _num(h.get("independent_contributors")))
        add("independent_reports", _num(h.get("independent_issue_reports")) + _num((r["bundle"]["outcome_summary"] or {}).get("yes")))
        add("forks", _num(h.get("forks")))
        if h.get("installs") is not None:
            add("installs", _num(h.get("installs")))
        if h.get("stargazer_quality") is not None:
            add("star_velocity_quality", _num(h.get("star_velocity_7d")) * _num(h.get("stargazer_quality")))
        if ver and isinstance(ver.get("delta"), (int, float)):
            add("behavioral_delta", ver["delta"])

    for r in rows:
        r["s"] = _signals(r["bundle"], raw, cid_cluster, r["cid"])
        pts = _points_for(set(r["s"].keys()))
        r["score"] = round(sum(pts.get(k, 0) * v for k, v in r["s"].items()), 3)
        r["has_verification"] = "behavioral_delta" in r["s"]

    # order: full by score, then partial by score; ties -> host level, evidence
    lvl_rank = {"compatible": 0, "partial": 1, "unknown": 2, "incompatible": 3}
    ev_rank = {"verified": 0, "tested-once": 1, "inspected": 2}

    def evidence_level(r):
        ver = r["bundle"]["verification"]
        if ver and ver.get("status") == "confirmed":
            return "verified"
        if ver and ver.get("status") == "single":
            return "tested-once"
        return "inspected"

    rows.sort(key=lambda r: (0 if r["fit"] == "full" else 1, -r["score"],
                             lvl_rank.get(r["level"], 2), ev_rank.get(evidence_level(r), 2)))

    picks = [_pick(r, host, evidence_level(r)) for r in rows[:3]]
    _apply_flags(rows[:3], picks, raw, cid_cluster)
    _gem_slot(short, picks, fits, store, host)

    out = {"task_label": task.get("task_label", ""), "host_harness": host,
           "none_found": len(picks) == 0, "picks": picks,
           "differentiator": _differentiator(rows[:len(picks)]),
           "set_aside": short["set_aside"], "not_evaluated": not_evaluated,
           "display_harnesses": short["display_harnesses"], "harness_names": short["harness_names"],
           "verification_available": short["verification_available"]}
    return out


def _pick(r, host, ev_level) -> dict:
    b, ev, cand = r["bundle"], r["bundle"]["evaluation"], r["bundle"]["candidate"]
    compat = (b["compatibility"] or {}).get("harness") or {}
    disp = {h: {"level": (compat.get(h) or {}).get("level", "unknown"),
                "reasons": (compat.get(h) or {}).get("reasons", [])} for h in _harness_meta(host)["display_harnesses"]}
    if host != "unknown":
        disp[host] = {"level": r["level"], "reasons": compat.get(host, {}).get("reasons", [])}
    claims = ev.get("claims", [])
    counts = {v: sum(1 for c in claims if c.get("verdict") == v) for v in ("supported", "unsupported", "unverifiable")}
    top_un = next((c["claim"] for c in claims if c.get("verdict") == "unsupported" and c.get("importance") == "core"), "")
    sha = cand.get("commit_sha", "")
    sp = cand.get("skill_path", ".")
    md = f"https://github.com/{cand['repo']}/blob/{sha}/{'' if sp == '.' else sp + '/'}SKILL.md"
    return {
        "candidate_id": r["cid"], "skill_name": cand.get("skill_name", ""), "repo": cand.get("repo", ""),
        "skill_path": sp,
        "install": {"command": f"Copy {cand['repo']}/{sp} (at {sha[:10]}) into your harness's skills folder",
                    "distribution": cand.get("distribution", "repo")},
        "fit": r["fit"], "missing": r["missing"], "badge": "established",
        "evidence_level": ev_level, "score": r["score"],
        "actually_does": ev.get("actually_does", ""), "features": ev.get("features", []),
        "limitations": ev.get("limitations", []),
        "claims_summary": {**counts, "top_unsupported": top_un},
        "compatibility": disp, "tested_on": [b["verification"]["harness"]] if b["verification"] else [],
        "requirements": (b["compatibility"] or {}).get("requirements", {}),
        "flags": [], "sources": [md],
    }


def _apply_flags(rows, picks, raw, cid_cluster):
    # popularity vs credibility percentile gap, and star_burst.
    for r, pick in zip(rows, picks):
        h = r["bundle"]["health"] or {}
        if "star_burst" in (h.get("flags") or []):
            pick["flags"].append("suspicious_popularity")
        cl = cid_cluster.get(r["cid"])
        pop_peers = raw.get((cl, "forks"), [])
        pop_pct = _pct(_num(h.get("forks")), pop_peers) * 100
        cred_peers = [credibility(x["bundle"]["evaluation"]) for x in rows]
        cred_pct = _pct(credibility(r["bundle"]["evaluation"]), cred_peers) * 100
        if pop_pct - cred_pct >= CFG["flags"]["unproven_gap_percentile"]:
            pick["flags"].append("popular_but_unproven")


def _gem_slot(short, picks, fits, store, host):
    """engines.md: the best qualifying new skill takes slot 3 (displacing the 3rd
    normal pick) when it isn't already in the top 3."""
    in_top = {p["candidate_id"] for p in picks[:3]}
    best = None
    for c in short["shortlist"]:
        cid = c["candidate_id"]
        if cid in in_top:
            continue
        f = fits.get(cid)
        if not f or f.get("fit") != "full":            # gem needs fit: full
            continue
        b = store.bundle(cid)
        if not b["evaluation"] or _days_ago((b["candidate"] or {}).get("first_seen") or "") > 14:
            continue
        if (b["health"] or {}).get("flags"):           # "no flags"
            continue
        if credibility(b["evaluation"]) < CFG["floor"]["min_credibility"] \
                or unsupported_core_count(b["evaluation"]) > CFG["floor"]["max_unsupported_core"]:
            continue
        gs = gem_score(b)
        if gs < CFG["gem"]["min_gem_score"]:
            continue
        if best is None or gs > best[1]:
            best = (cid, gs, b)
    if not best:
        return
    cid, gs, b = best
    lvl, _ = effective_level(b, host) if host != "unknown" else ("unknown", [])
    if host != "unknown" and lvl == "incompatible":
        return
    r = {"cid": cid, "bundle": b, "fit": "full", "missing": [], "level": lvl, "score": round(gs, 3)}
    pick = _pick(r, host, "inspected")
    pick["badge"] = "hidden-gem"
    if len(picks) < 3:
        picks.append(pick)
    else:
        picks[2] = pick                                # displace the 3rd normal pick


def _differentiator(rows):
    if len(rows) < 2:
        return {"signal": "", "first": 0.0, "second": 0.0}
    pts = _points_for(set(rows[0].get("s", {}).keys()))
    best = ("", 0.0, 0.0, -1.0)
    for k in rows[0].get("s", {}):
        a = pts.get(k, 0) * rows[0]["s"].get(k, 0)
        bv = pts.get(k, 0) * rows[1]["s"].get(k, 0)
        if abs(a - bv) > best[3]:
            best = (k, round(rows[0]["s"].get(k, 0), 3), round(rows[1]["s"].get(k, 0), 3), abs(a - bv))
    return {"signal": best[0], "first": best[1], "second": best[2]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rank.py")
    ap.add_argument("cmd", choices=["task-template", "retrieve", "rank"])
    ap.add_argument("--task")
    ap.add_argument("--fits")
    ap.add_argument("--index")
    a = ap.parse_args(argv)
    if a.cmd == "task-template":
        print(json.dumps(TASK_TEMPLATE, indent=2))
        return 0
    task = json.loads(Path(a.task).read_text(encoding="utf-8"))
    store = store_mod.get_store(index_path=a.index)
    try:
        if a.cmd == "retrieve":
            print(json.dumps(retrieve(task, store), indent=2))
        else:
            fits_list = json.loads(Path(a.fits).read_text(encoding="utf-8"))
            fits = {f["candidate_id"]: f for f in fits_list}
            print(json.dumps(rank(task, fits, store), indent=2))
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
