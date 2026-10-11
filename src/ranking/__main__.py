"""Ranking engine jobs (stage 08), run by GitHub Actions — no LLM.

    python -m src.ranking gem       # daily: gem leaderboard over new skills
    python -m src.ranking famous    # weekly: refresh anti-gaming flags on older skills
    python -m src.ranking --stats

The authoritative gem-slot and flag decisions happen in rank.py at query time
(scoring.md steps 9-10); these jobs precompute/report over the whole index for
monitoring and the v2 shared cache. They reuse the shipped rank.py/store.py (the
same code the skill runs) over the pipeline DB.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from src.db.core.db import DEFAULT_DB, connect, migrate

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "skill-scout" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import rank as rank_mod          # noqa: E402
import store as store_mod        # noqa: E402

NEW_SKILL_DAYS = 14


def _store():
    return store_mod.get_store(index_path=DEFAULT_DB, local_path=DEFAULT_DB.parent / "server_local.sqlite")


def gem_job(conn) -> dict:
    cfg = rank_mod.CFG["gem"]
    store = _store()
    board = []
    for r in conn.execute("SELECT candidate_id, first_seen FROM candidate WHERE status='active'"):
        if not r["first_seen"] or rank_mod._days_ago(r["first_seen"]) > NEW_SKILL_DAYS:
            continue
        b = store.bundle(r["candidate_id"])
        if not b["evaluation"]:
            continue                     # v1: new skills are evaluated in the user's own session
        gs = rank_mod.gem_score(b)
        board.append({"candidate_id": r["candidate_id"], "gem_score": round(gs, 3),
                      "badge_eligible": gs >= cfg["min_gem_score"]})
    store.close()
    board.sort(key=lambda x: -x["gem_score"])
    return {"new_skills_scored": len(board), "badge_eligible": sum(b["badge_eligible"] for b in board),
            "top": board[:10]}


def famous_job(conn) -> dict:
    cfg = rank_mod.CFG["famous"]
    flagged = {}
    for r in conn.execute("SELECT candidate_id, first_seen FROM candidate WHERE status='active'"):
        if not r["first_seen"] or rank_mod._days_ago(r["first_seen"]) <= cfg["min_age_days"]:
            continue
        h = conn.execute("SELECT flags FROM health WHERE candidate_id=?", (r["candidate_id"],)).fetchone()
        for f in (json.loads(h["flags"]) if h and h["flags"] else []):
            flagged[f] = flagged.get(f, 0) + 1
    return {"older_skills_flag_counts": flagged}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="python -m src.ranking")
    ap.add_argument("job", nargs="?", choices=["gem", "famous"])
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)
    conn = connect()
    migrate(conn)
    if a.stats or not a.job:
        print({"candidates": conn.execute("SELECT COUNT(*) FROM candidate WHERE status='active'").fetchone()[0],
               "external_reports": conn.execute("SELECT COUNT(*) FROM external_reports").fetchone()[0],
               "outcome_reports": conn.execute("SELECT COUNT(*) FROM outcome_reports").fetchone()[0]})
        return 0
    print(json.dumps(gem_job(conn) if a.job == "gem" else famous_job(conn)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
