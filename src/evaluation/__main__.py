"""Evaluation: import committed seeds (build) and seed new ones (owner only).

    python -m src.evaluation            # import data/seed/evaluations/*.json into the DB (no LLM)
    python -m src.evaluation --stats
    python -m src.evaluation seed <candidate_id> [...] [--model M]   # owner machine only; makes LLM calls

The scheduled build runs the no-arg form: it imports every committed seed and
marks each active or stale by comparing its content_hash to the current
candidate. Seeding runs only on the owner's machine within the CLAUDE.md budget,
never in GitHub Actions; it writes one validated JSON per evaluation to
data/seed/evaluations/ for the owner to review and commit.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.db.core.db import REPO_ROOT, connect, migrate

SEED_DIR = REPO_ROOT / "data" / "seed" / "evaluations"
SCRIPTS = REPO_ROOT / "skills" / "skill-scout" / "scripts"
RUBRIC = REPO_ROOT / "skills" / "skill-scout" / "references" / "evaluation-rubric.md"
DEFAULT_MODEL = "claude-haiku-4-5"     # the model the seeding cost estimate is based on; override with --model

COLUMNS = ["candidate_id", "content_hash", "commit_sha", "evaluator_model", "actually_does",
           "capabilities", "claims", "features", "limitations", "issue_resolution",
           "instruction_specificity", "example_realism", "hype_score", "core_depends_on",
           "injection_detected", "injection_detail", "evaluator_confidence",
           "status", "source_file", "imported_at"]
_JSON_FIELDS = {"capabilities", "claims", "features", "limitations", "issue_resolution", "core_depends_on"}


def _row(rec: dict, status: str, source_file: str) -> list:
    out = []
    for c in COLUMNS:
        if c == "status":
            out.append(status)
        elif c == "source_file":
            out.append(source_file)
        elif c == "imported_at":
            out.append(datetime.now(timezone.utc).isoformat())
        elif c in _JSON_FIELDS:
            out.append(json.dumps(rec.get(c, [] if c != "issue_resolution" else {})))
        elif c == "injection_detected":
            out.append(1 if rec.get("injection_detected") else 0)
        else:
            out.append(rec.get(c))
    return out


def import_seeds(conn) -> dict:
    current = {r["candidate_id"]: r["content_hash"]
               for r in conn.execute("SELECT candidate_id, content_hash FROM candidate")}
    cols = ",".join(COLUMNS)
    ph = ",".join("?" for _ in COLUMNS)
    sets = ",".join(f"{c}=excluded.{c}" for c in COLUMNS if c not in ("candidate_id", "content_hash"))
    n = stale = 0
    for f in sorted(SEED_DIR.glob("*.json")) if SEED_DIR.exists() else []:
        rec = json.loads(f.read_text(encoding="utf-8"))
        cid, ch = rec.get("candidate_id"), rec.get("content_hash")
        if not cid or not ch:
            print(f"skip {f.name}: missing candidate_id/content_hash", file=sys.stderr)
            continue
        status = "active" if current.get(cid) == ch else "stale"   # changed content (or not yet collected) -> stale
        stale += status == "stale"
        conn.execute(f"INSERT INTO evaluation ({cols}) VALUES ({ph}) "
                     f"ON CONFLICT(candidate_id, content_hash) DO UPDATE SET {sets}",
                     _row(rec, status, f.name))
        n += 1
    conn.commit()
    return {"imported": n, "stale": stale}


# ---- seeding (owner machine only) --------------------------------------------
def _evaluate(evidence: str, model: str) -> dict:
    import anthropic                                   # lazy: seed-only optional dep
    client = anthropic.Anthropic()                     # ANTHROPIC_API_KEY from env
    msg = client.messages.create(model=model, max_tokens=2000,
                                 system=RUBRIC.read_text(encoding="utf-8"),
                                 messages=[{"role": "user", "content": evidence}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def seed(conn, candidate_ids: list[str], model: str) -> dict:
    if os.environ.get("GITHUB_ACTIONS"):
        print("refusing to seed inside GitHub Actions (CLAUDE.md: seeding is owner-only)", file=sys.stderr)
        return {"seeded": 0}
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    done = []
    for cid in candidate_ids:
        row = conn.execute("SELECT candidate_id, content_hash, commit_sha FROM candidate WHERE candidate_id=?",
                           (cid,)).fetchone()
        if not row:
            print(f"skip {cid}: not in candidate table", file=sys.stderr)
            continue
        evidence = subprocess.run([sys.executable, str(SCRIPTS / "fetch_evidence.py"), cid],
                                  capture_output=True, text=True, check=True).stdout
        for attempt in range(2):                       # validate; retry once
            rec = _evaluate(evidence, model)
            rec.update({"candidate_id": cid, "content_hash": row["content_hash"], "commit_sha": row["commit_sha"]})
            out = SEED_DIR / f"{cid.replace('/', '__').replace('@', '__')}__{row['content_hash'][:12]}.json"
            out.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            v = subprocess.run([sys.executable, str(SCRIPTS / "validate_evaluation.py"), str(out)],
                               capture_output=True, text=True)
            if v.returncode == 0:
                done.append(cid)
                break
            print(f"{cid}: validation failed (attempt {attempt + 1}): {v.stderr.strip()}", file=sys.stderr)
        else:
            out.unlink(missing_ok=True)
    return {"seeded": len(done)}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(prog="python -m src.evaluation")
    ap.add_argument("cmd", nargs="?", default="import", choices=["import", "seed"])
    ap.add_argument("candidate_ids", nargs="*")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)

    conn = connect()
    migrate(conn)
    if a.stats:
        print({"evaluations": conn.execute("SELECT COUNT(*) FROM evaluation").fetchone()[0],
               "active": conn.execute("SELECT COUNT(*) FROM evaluation WHERE status='active'").fetchone()[0],
               "stale": conn.execute("SELECT COUNT(*) FROM evaluation WHERE status='stale'").fetchone()[0]})
        return 0
    result = seed(conn, a.candidate_ids, a.model) if a.cmd == "seed" else import_seeds(conn)
    conn.close()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
