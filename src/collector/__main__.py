"""Collector entrypoint for the scheduled build.

    python -m src.collector            # daily sweep (new/changed skills)
    python -m src.collector --full     # weekly full refresh (reprocess all)
    python -m src.collector --limit 20 # dev: stop after 20 accepted
    python -m src.collector --stats    # print DB counts and exit

Auth comes from env AF_GITHUB_TOKEN (see sources.md). The safety scanner, if
any, comes from env AF_SAFETY_SCANNER (see safety.py).
"""
from __future__ import annotations
import argparse
import sys

from src.collector import discovery, pipeline
from src.db.core.db import connect, migrate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.collector")
    ap.add_argument("--full", action="store_true", help="full refresh (reprocess all)")
    ap.add_argument("--limit", type=int, default=None, help="stop after N accepted (dev)")
    ap.add_argument("--repos", help="comma-separated repos to sweep (dev; skips discovery)")
    ap.add_argument("--no-dates", action="store_true", help="skip first/last commit lookups (faster dev)")
    ap.add_argument("--no-resume", action="store_true", help="ignore a saved cursor; start fresh")
    ap.add_argument("--stats", action="store_true", help="print DB counts and exit")
    a = ap.parse_args(argv)

    conn = connect()
    migrate(conn)
    if a.stats:
        c = conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
        r = conn.execute("SELECT COUNT(*) FROM reject").fetchone()[0]
        print(f"candidates={c} rejects={r}")
        return 0

    repos = [s.strip() for s in a.repos.split(",")] if a.repos else None
    if not discovery._token() and repos is None:
        print("warning: no AF_GITHUB_TOKEN; discovery limited to known collections "
              "under anonymous rate limits.", file=sys.stderr)
    try:
        stats = pipeline.run_sweep(conn, repos=repos, full=a.full, limit=a.limit,
                                   with_dates=not a.no_dates, resume=not a.no_resume)
    except discovery.RateLimited as e:
        print(f"rate limited; cursor saved, resume next run (reset {e.reset_epoch})", file=sys.stderr)
        return 75  # EX_TEMPFAIL
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
