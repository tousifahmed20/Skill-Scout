"""Content hashing and dedupe.

content_hash (definition: CLAUDE.md) = sha256 over every file in the skill
folder, paths sorted, LF line endings. LF normalization makes a CRLF checkout
on the owner's Windows box hash identically to an LF checkout in CI.

Dedupe: same content_hash -> one canonical candidate (earliest first commit);
forks and mirrors therefore collapse into their source, which is older.
"""
from __future__ import annotations
import hashlib


def content_hash(files: dict[str, bytes]) -> str:
    """files maps folder-relative path -> raw bytes."""
    h = hashlib.sha256()
    for path in sorted(files):
        data = files[path].replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
    return h.hexdigest()


def collapse(candidates: list[dict]) -> tuple[list[dict], int]:
    """Group by content_hash; keep the earliest-first_seen row as canonical and
    record the rest in its `duplicates`. Returns (canonicals, collapsed_count).

    Tie-break on candidate_id so the choice is deterministic when first_seen is
    equal or missing.
    """
    groups: dict[str, list[dict]] = {}
    for c in candidates:
        groups.setdefault(c["content_hash"], []).append(c)

    canonicals, collapsed = [], 0
    for rows in groups.values():
        rows.sort(key=lambda c: (c.get("first_seen") or "9999-12-31", c["candidate_id"]))
        canon, dups = rows[0], rows[1:]
        existing = list(canon.get("duplicates") or [])
        canon["duplicates"] = existing + [d["candidate_id"] for d in dups]
        collapsed += len(dups)
        canonicals.append(canon)
    return canonicals, collapsed
