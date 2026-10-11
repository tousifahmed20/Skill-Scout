"""Populate the compatibility table from stored candidates and their checkouts.

    python -m src.compatibility           # check all active candidates
    python -m src.compatibility --limit 50
    python -m src.compatibility --stats

Static analysis only (no execution, no LLM). Reads each skill from the stage-02
checkout under data/cache/skills/...; skips candidates not yet checked out.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.compatibility.checker import check_candidate, load_profiles
from src.db.core.db import REPO_ROOT, connect, migrate

CACHE_ROOT = REPO_ROOT / "data" / "cache" / "skills"
TEXT_EXT = {".md", ".py", ".sh", ".bash", ".js", ".ts", ".mjs", ".cjs", ".ps1",
            ".json", ".yaml", ".yml", ".toml", ".txt", ".html", ".css"}


def _checkout_dir(repo: str, skill_path: str, commit_sha: str) -> Path:
    sub = "" if skill_path == "." else skill_path
    return CACHE_ROOT / repo.replace("/", "__") / commit_sha / sub


def _load_checkout(d: Path):
    files, texts, skill_md = [], {}, None
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(d).as_posix()
        files.append(rel)
        if rel == "SKILL.md":
            skill_md = p.read_text(encoding="utf-8", errors="replace")
        elif p.suffix.lower() in TEXT_EXT:
            try:
                texts[rel] = p.read_text(encoding="utf-8")
            except OSError:
                pass
    return skill_md, files, texts


def _upsert(conn, rec: dict) -> None:
    conn.execute(
        "INSERT INTO compatibility (candidate_id, content_hash, harness, requirements, "
        "declared_compatibility, declared_conflict) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(candidate_id) DO UPDATE SET content_hash=excluded.content_hash, "
        "harness=excluded.harness, requirements=excluded.requirements, "
        "declared_compatibility=excluded.declared_compatibility, "
        "declared_conflict=excluded.declared_conflict",
        (rec["candidate_id"], rec["content_hash"], json.dumps(rec["harness"]),
         json.dumps(rec["requirements"]), json.dumps(rec["declared_compatibility"]),
         1 if rec["declared_conflict"] else 0),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.compatibility")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)

    conn = connect()
    migrate(conn)
    if a.stats:
        print("compatibility rows:", conn.execute("SELECT COUNT(*) FROM compatibility").fetchone()[0])
        return 0

    profiles = load_profiles()
    rows = conn.execute("SELECT candidate_id, repo, skill_path, commit_sha, content_hash "
                        "FROM candidate WHERE status='active'").fetchall()
    done = missing = 0
    for r in rows:
        d = _checkout_dir(r["repo"], r["skill_path"], r["commit_sha"])
        skill_md, files, texts = _load_checkout(d)
        if skill_md is None:
            missing += 1
            continue
        rec = check_candidate(dict(r), skill_md, files, profiles, texts)
        _upsert(conn, rec)
        done += 1
        if a.limit and done >= a.limit:
            break
    conn.commit()
    print({"checked": done, "missing_checkout": missing})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
