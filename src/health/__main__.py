"""Compute health signals for active candidates and store them.

    python -m src.health              # refresh stale candidates (weekly; daily if new)
    python -m src.health --limit 50
    python -m src.health --force      # recompute all active candidates
    python -m src.health --stats

Staleness (CLAUDE.md cadence): recompute when there is no health row, the
candidate's content_hash changed, or the row is older than 7 days (1 day for a
new skill, first_seen <= 14d ago). On a far-off rate-limit reset the run commits
what it has and stops; next run resumes by staleness. No execution, no LLM.
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone

from src.collector.discovery import RateLimited
from src.health.compute import NEW_SKILL_DAYS, compute, _age_days, _parse
from src.health.fetch import build_raw
from src.db.core.db import connect, migrate

WEEKLY_H = 7 * 24
NEW_DAILY_H = 24

COLUMNS = ["candidate_id", "content_hash", "computed_at", "independent_issue_reports",
           "linked_fix_closures", "closed_without_fix", "substantive_commits_90d",
           "median_diff_lines", "contributors", "independent_contributors",
           "maintainer_first_response_h", "stars", "star_velocity_7d", "stargazer_quality",
           "installs", "forks", "releases", "license", "archived", "last_commit",
           "author_track_record", "early_organic_traction", "scope", "flags"]


def _stale(cand: dict, health: dict | None, now: datetime) -> bool:
    if health is None or health["content_hash"] != cand["content_hash"]:
        return True
    age_h = ((now - d).total_seconds() / 3600) if (d := _parse(health["computed_at"])) else 1e9
    is_new = (a := _age_days(cand["first_seen"], now)) is not None and a <= NEW_SKILL_DAYS
    return age_h >= (NEW_DAILY_H if is_new else WEEKLY_H)


def _upsert(conn, rec: dict) -> None:
    rec = {**rec, "archived": 1 if rec["archived"] else 0,
           "scope": json.dumps(rec["scope"]), "flags": json.dumps(rec["flags"])}
    cols = ",".join(COLUMNS)
    ph = ",".join("?" for _ in COLUMNS)
    sets = ",".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "candidate_id")
    conn.execute(f"INSERT INTO health ({cols}) VALUES ({ph}) "
                 f"ON CONFLICT(candidate_id) DO UPDATE SET {sets}",
                 [rec.get(c) for c in COLUMNS])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.health")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="recompute all, ignore staleness")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)

    conn = connect()
    migrate(conn)
    if a.stats:
        n = conn.execute("SELECT COUNT(*) FROM health").fetchone()[0]
        flagged = conn.execute("SELECT COUNT(*) FROM health WHERE flags != '[]'").fetchone()[0]
        print({"health_rows": n, "flagged": flagged})
        return 0

    now = datetime.now(timezone.utc)
    cands = conn.execute("SELECT candidate_id, repo, skill_path, skill_name, distribution, "
                         "first_seen, content_hash FROM candidate WHERE status='active'").fetchall()
    health = {r["candidate_id"]: dict(r) for r in
              conn.execute("SELECT candidate_id, content_hash, computed_at FROM health")}

    done = skipped = failed = 0
    try:
        for r in cands:
            cand = dict(r)
            if not a.force and not _stale(cand, health.get(cand["candidate_id"]), now):
                skipped += 1
                continue
            try:
                rec = compute(build_raw(cand, now))
            except RateLimited as e:
                conn.commit()
                print({"stopped": "rate_limited", "resume_after": e.reset_epoch,
                       "computed": done, "skipped": skipped, "failed": failed})
                return 0
            except Exception as ex:   # noqa: BLE001 - one bad repo must not sink the sweep
                failed += 1
                print(f"skip {cand['candidate_id']}: {type(ex).__name__}: {ex}")
                continue
            _upsert(conn, rec)
            done += 1
            if a.limit and done >= a.limit:
                break
        conn.commit()
    finally:
        conn.close()
    print({"computed": done, "skipped_fresh": skipped, "failed": failed})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
