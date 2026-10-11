"""Text search for the shipped skill (stage 05). Standard library only, so the
skill installs nothing and runs on Windows and Linux.

Document per skill = name + description + SKILL.md first section + cluster labels
+ (when an evaluation exists) capabilities + actually_does. The model writes the
query (`search_terms` + `capabilities`) with synonyms, so wording differences do
not hide good skills — queries use OR semantics for recall.

Ranking: SQLite FTS5 + bm25() when this sqlite build has FTS5; otherwise a pure
-Python BM25 over the stored documents. Both read the same `search_doc` table,
so one published index serves either runtime.
"""
from __future__ import annotations
import math
import re
import sqlite3

K_DEFAULT = 30
_TOKEN = re.compile(r"[a-z0-9]+")
# BM25 constants (Robertson/Spärck Jones); standard defaults.
_K1, _B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def doc_text(doc: dict) -> str:
    """Flatten a skill's searchable fields into one blob (missing fields skipped)."""
    parts = [doc.get("name", ""), doc.get("description", ""), doc.get("first_section", "")]
    for key in ("labels", "capabilities", "actually_does"):
        v = doc.get(key)
        if isinstance(v, (list, tuple)):
            parts.append(" ".join(str(x) for x in v))
        elif v:
            parts.append(str(v))
    return "\n".join(p for p in parts if p)


def fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def build_index(conn: sqlite3.Connection, docs: list[dict]) -> str:
    """(Re)build the search index from docs. Returns the backend used.
    `search_doc` is always written (the fallback source); `search_fts` is added
    when FTS5 is available at build time."""
    conn.execute("CREATE TABLE IF NOT EXISTS search_doc (candidate_id TEXT PRIMARY KEY, text TEXT NOT NULL)")
    conn.execute("DELETE FROM search_doc")
    conn.executemany("INSERT OR REPLACE INTO search_doc (candidate_id, text) VALUES (?,?)",
                     [(d["candidate_id"], doc_text(d)) for d in docs])
    backend = "python-bm25"
    if fts5_available(conn):
        conn.execute("DROP TABLE IF EXISTS search_fts")
        conn.execute("CREATE VIRTUAL TABLE search_fts USING fts5(candidate_id UNINDEXED, text)")
        conn.execute("INSERT INTO search_fts (candidate_id, text) SELECT candidate_id, text FROM search_doc")
        backend = "fts5"
    conn.commit()
    return backend


def _match_query(tokens: list[str]) -> str:
    # alnum tokens only (tokenize guarantees it) -> safe to OR together for recall
    return " OR ".join(dict.fromkeys(tokens))


def _search_fts5(conn: sqlite3.Connection, tokens: list[str], k: int) -> list[str]:
    rows = conn.execute(
        "SELECT candidate_id FROM search_fts WHERE search_fts MATCH ? ORDER BY bm25(search_fts) LIMIT ?",
        (_match_query(tokens), k)).fetchall()
    return [r[0] for r in rows]


def _search_python(conn: sqlite3.Connection, tokens: list[str], k: int) -> list[str]:
    """BM25 over search_doc, OR semantics. Recomputes per query — fine at index
    sizes we publish (a few thousand short docs). ponytail: precompute postings
    if a profile ever shows this hot."""
    docs = conn.execute("SELECT candidate_id, text FROM search_doc").fetchall()
    toks = [(cid, tokenize(text)) for cid, text in docs]
    n = len(toks)
    if not n:
        return []
    avg_len = sum(len(t) for _, t in toks) / n
    q = set(tokens)
    df = {w: sum(1 for _, t in toks if w in t) for w in q}
    scored = []
    for cid, t in toks:
        tl = len(t) or 1
        score = 0.0
        for w in q:
            tf = t.count(w)
            if not tf or not df.get(w):
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            score += idf * (tf * (_K1 + 1)) / (tf + _K1 * (1 - _B + _B * tl / avg_len))
        if score > 0:
            scored.append((score, cid))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [cid for _, cid in scored[:k]]


def search(conn: sqlite3.Connection, terms: str, k: int = K_DEFAULT, capabilities: str = "") -> list[str]:
    """Return candidate_ids by relevance for the query (terms + capabilities)."""
    tokens = tokenize(f"{terms} {capabilities}")
    if not tokens:
        return []
    use_fts = fts5_available(conn) and \
        conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_fts'").fetchone()
    return (_search_fts5 if use_fts else _search_python)(conn, tokens, k)
