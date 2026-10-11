"""One collection sweep: discover -> membership -> safety -> checkout -> store,
then a global dedupe pass. Resumable via the sweep_state cursor so a rate-limit
or crash never drops work (sources.md).

Dedupe is global (forks live in different repos), so it runs once after the
sweep over all stored candidates, not per repo.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from src.collector import discovery, membership, safety
from src.collector.dedupe import collapse, content_hash
from src.db.core.db import REPO_ROOT

CACHE_ROOT = REPO_ROOT / "data" / "cache" / "skills"
LIST_JSON = ("frontmatter_keys", "spec_warnings", "duplicates")


def _folder_name(repo: str, skill_path: str) -> str:
    return repo.split("/")[-1] if skill_path == "." else skill_path.rsplit("/", 1)[-1]


def checkout(raw: discovery.RawSkill) -> Path:
    owner_repo = raw.repo.replace("/", "__")
    sub = "" if raw.skill_path == "." else raw.skill_path
    dest = CACHE_ROOT / owner_repo / raw.commit_sha / sub
    for rel, data in raw.files.items():
        p = dest / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return dest


def _upsert_candidate(conn, c: dict) -> None:
    cols = ["candidate_id", "repo", "skill_path", "skill_name", "description",
            "distribution", "plugin_manifest", "first_seen", "last_changed",
            "commit_sha", "content_hash", "frontmatter_keys", "spec_warnings",
            "files", "duplicates", "safety", "status"]
    row = dict(c)
    for k in ("frontmatter_keys", "spec_warnings", "duplicates", "files", "safety"):
        row[k] = json.dumps(row.get(k) if row.get(k) is not None else ([] if k in LIST_JSON else {}))
    conn.execute(
        f"INSERT INTO candidate ({','.join(cols)}) VALUES ({','.join('?'*len(cols))}) "
        f"ON CONFLICT(candidate_id) DO UPDATE SET "
        + ",".join(f"{k}=excluded.{k}" for k in cols if k != "candidate_id"),
        [row[k] for k in cols],
    )


def _upsert_reject(conn, location: str, reason: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO reject (location, reason, detail, seen_on) VALUES (?,?,?,date('now')) "
        "ON CONFLICT(location) DO UPDATE SET reason=excluded.reason, detail=excluded.detail, "
        "seen_on=excluded.seen_on",
        (location, reason, detail),
    )


def _already_current(conn, candidate_id: str, commit_sha: str) -> bool:
    r = conn.execute("SELECT commit_sha FROM candidate WHERE candidate_id=?",
                     (candidate_id,)).fetchone()
    return bool(r and r["commit_sha"] == commit_sha)


def _load_cursor(conn, sweep: str, repos: list[str], resume: bool):
    if resume:
        row = conn.execute("SELECT queue, done FROM sweep_state WHERE sweep=?", (sweep,)).fetchone()
        if row and json.loads(row["queue"]):
            return json.loads(row["queue"]), set(json.loads(row["done"]))
    conn.execute(
        "INSERT INTO sweep_state (sweep, queue, done, updated) VALUES (?,?,'[]',datetime('now')) "
        "ON CONFLICT(sweep) DO UPDATE SET queue=excluded.queue, done='[]', updated=excluded.updated",
        (sweep, json.dumps(repos)),
    )
    conn.commit()
    return list(repos), set()


def _save_cursor(conn, sweep: str, queue: list[str], done: set) -> None:
    conn.execute("UPDATE sweep_state SET queue=?, done=?, updated=datetime('now') WHERE sweep=?",
                 (json.dumps(queue), json.dumps(sorted(done)), sweep))
    conn.commit()


def dedupe_db(conn) -> int:
    rows = [dict(r) for r in conn.execute(
        "SELECT candidate_id, content_hash, first_seen, duplicates FROM candidate "
        "WHERE status='active'")]
    for r in rows:
        r["duplicates"] = json.loads(r["duplicates"])
    canonicals, collapsed = collapse(rows)
    keep = {c["candidate_id"] for c in canonicals}
    for c in canonicals:
        conn.execute("UPDATE candidate SET duplicates=? WHERE candidate_id=?",
                     (json.dumps(c["duplicates"]), c["candidate_id"]))
    for r in rows:
        if r["candidate_id"] not in keep:
            conn.execute("DELETE FROM candidate WHERE candidate_id=?", (r["candidate_id"],))
    conn.commit()
    return collapsed


def run_sweep(conn, repos: list[str] | None = None, *, full: bool = False,
              limit: int | None = None, with_dates: bool = True,
              scanner_cmd: str | None = None, resume: bool = True) -> dict:
    sweep = "full" if full else "daily"
    repos = repos if repos is not None else discovery.discover_repos()
    queue, done = _load_cursor(conn, sweep, repos, resume)
    stats = {"accepted": 0, "rejected": 0, "skipped_unchanged": 0, "excluded_unsafe": 0}

    while queue:
        repo = queue[0]
        try:
            metas = discovery.enumerate_repo(repo)
            for meta in metas:
                cid = f"{repo}@{meta['skill_path']}"
                if not full and _already_current(conn, cid, meta["commit_sha"]):
                    stats["skipped_unchanged"] += 1
                    continue
                raw = discovery.fetch_skill(repo, meta, with_dates=with_dates)
                res = membership.evaluate(raw.folder_files, raw.skill_md_text,
                                          _folder_name(repo, raw.skill_path))
                if not res.accepted:
                    _upsert_reject(conn, cid, res.reason, res.detail)
                    stats["rejected"] += 1
                    continue
                dest = checkout(raw)
                safety_res = safety.scan(dest, scanner_cmd)
                status = safety.candidate_status(safety_res)
                _upsert_candidate(conn, {
                    "candidate_id": cid, "repo": repo, "skill_path": raw.skill_path,
                    "skill_name": res.name, "description": res.description,
                    "distribution": raw.distribution, "plugin_manifest": raw.plugin_manifest,
                    "first_seen": raw.first_seen, "last_changed": raw.last_changed,
                    "commit_sha": raw.commit_sha, "content_hash": content_hash(raw.files),
                    "frontmatter_keys": res.frontmatter_keys, "spec_warnings": res.spec_warnings,
                    "files": raw.files_categorized, "duplicates": [],
                    "safety": safety_res, "status": status,
                })
                stats["accepted" if status == "active" else "excluded_unsafe"] += 1
                if limit and stats["accepted"] >= limit:
                    queue = []
                    break
        except discovery.RateLimited:
            _save_cursor(conn, sweep, queue, done)
            raise
        done.add(repo)
        queue = queue[1:]
        _save_cursor(conn, sweep, queue, done)

    stats["collapsed_duplicates"] = dedupe_db(conn)
    stats["total_candidates"] = conn.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
    return stats
