#!/usr/bin/env python3
"""Store interface + `local` backend (stage 08). Standard library only.

`local` (the v1 default) reads the published index at the skill cache path and
overlays the user's own results from local.sqlite; nothing leaves the machine.
`put` writes only to local.sqlite. The `remote` backend is stage 10 (v2).

    Store.search(terms, k)     -> [(candidate_id, relevance)]
    Store.bundle(candidate_id) -> {candidate, compatibility, health,
                                   evaluation|null, evaluation_freshness, verification|null,
                                   outcome_summary}
    Store.put(kind, record)    -> {accepted, reason}   kind: evaluation|verification|outcome_report
"""
from __future__ import annotations
import json
import math
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")
_K1, _B = 1.5, 0.75
PUT_KINDS = {"evaluation", "verification", "outcome_report"}
# Canonical published index (GitHub Releases, latest). Override with SKILL_SCOUT_INDEX_URL.
DEFAULT_INDEX_URL = "https://github.com/tousifahmed20/Skill-Scout/releases/latest/download/index.sqlite.gz"


def _default_index() -> Path:
    return Path(os.environ.get("SKILL_SCOUT_INDEX") or (Path.home() / ".skill-scout" / "index.sqlite"))


def _default_local() -> Path:
    return Path(os.environ.get("SKILL_SCOUT_LOCAL") or (Path.home() / ".skill-scout" / "local.sqlite"))


def get_store(index_path: Path | None = None, local_path: Path | None = None) -> "LocalStore":
    backend = os.environ.get("SKILL_SCOUT_STORE", "local")
    if backend != "local":
        raise NotImplementedError(f"store backend '{backend}' is stage 10 (v2); v1 ships 'local'")
    return LocalStore(index_path, local_path)


class LocalStore:
    def __init__(self, index_path: Path | None = None, local_path: Path | None = None):
        self.index_path = Path(index_path) if index_path else _default_index()
        self.local_path = Path(local_path) if local_path else _default_local()
        self._maybe_download()
        if not self.index_path.exists():
            raise FileNotFoundError(f"index not found at {self.index_path}")
        self.ix = sqlite3.connect(self.index_path)
        self.ix.row_factory = sqlite3.Row
        self.local_path.parent.mkdir(parents=True, exist_ok=True)   # fresh machine may lack ~/.skill-scout
        self.local = sqlite3.connect(self.local_path)
        self.local.row_factory = sqlite3.Row
        self._init_local()

    # ponytail: v1 refreshes the index from the latest GitHub Release when it is
    # missing or >24h old. Auto-fetch only for the default user-cache path (real
    # installs); dev/tests pass an explicit non-default index path, so no-op there.
    def _maybe_download(self) -> None:
        url = os.environ.get("SKILL_SCOUT_INDEX_URL")
        if not url and self.index_path == _default_index():
            url = DEFAULT_INDEX_URL
        if not url:
            return
        fresh = self.index_path.exists() and (time.time() - self.index_path.stat().st_mtime) < 24 * 3600
        if fresh:
            return
        import gzip
        import urllib.request
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as r:
            data = gzip.decompress(r.read()) if url.endswith(".gz") else r.read()
        self.index_path.write_bytes(data)

    def _init_local(self) -> None:
        self.local.executescript(
            "CREATE TABLE IF NOT EXISTS local_evaluation (candidate_id TEXT, content_hash TEXT, json TEXT,"
            " PRIMARY KEY (candidate_id, content_hash));"
            "CREATE TABLE IF NOT EXISTS local_verification (candidate_id TEXT, content_hash TEXT, json TEXT,"
            " created_at TEXT);"
            "CREATE TABLE IF NOT EXISTS local_outcome (candidate_id TEXT, worked TEXT, harness TEXT,"
            " note TEXT, contributor_id TEXT, created_at TEXT);")
        self.local.commit()

    # ---- search --------------------------------------------------------------
    def _has(self, conn, table: str) -> bool:
        return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
                                 (table,)).fetchone())

    def search(self, terms, k: int = 30):
        text = terms if isinstance(terms, str) else " ".join(terms)
        toks = list(dict.fromkeys(_TOKEN.findall(text.lower())))
        if not toks:
            return []
        if self._has(self.ix, "search_fts"):
            try:
                rows = self.ix.execute(
                    "SELECT candidate_id, bm25(search_fts) b FROM search_fts WHERE search_fts MATCH ? "
                    "ORDER BY b LIMIT ?", (" OR ".join(toks), k)).fetchall()
                # bm25 is negative (better = more negative); map to 0..1 relevance.
                return [(r["candidate_id"], round(1.0 / (1.0 + math.exp(r["b"])), 4)) for r in rows]
            except sqlite3.OperationalError:
                pass
        return self._search_python(toks, k)

    def _search_python(self, toks, k):
        docs = self.ix.execute("SELECT candidate_id, text FROM search_doc").fetchall() \
            if self._has(self.ix, "search_doc") else []
        parsed = [(d["candidate_id"], _TOKEN.findall(d["text"].lower())) for d in docs]
        n = len(parsed)
        if not n:
            return []
        avg = sum(len(t) for _, t in parsed) / n
        q = set(toks)
        df = {w: sum(1 for _, t in parsed if w in t) for w in q}
        scored = []
        for cid, t in parsed:
            tl = len(t) or 1
            s = 0.0
            for w in q:
                tf = t.count(w)
                if tf and df.get(w):
                    idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                    s += idf * (tf * (_K1 + 1)) / (tf + _K1 * (1 - _B + _B * tl / avg))
            if s > 0:
                scored.append((cid, s))
        scored.sort(key=lambda x: (-x[1], x[0]))
        top = scored[:k]
        hi = top[0][1] if top else 1.0
        return [(cid, round(s / hi, 4)) for cid, s in top]

    # ---- bundle --------------------------------------------------------------
    def _one(self, conn, sql, args=()):
        if not self._has(conn, sql.split("FROM")[1].split()[0]):
            return None
        r = conn.execute(sql, args).fetchone()
        return dict(r) if r else None

    def _primary_cluster(self, cid):
        if not self._has(self.ix, "cluster_member"):
            return None
        r = self.ix.execute("SELECT cluster_id FROM cluster_member WHERE candidate_id=? "
                            "ORDER BY similarity DESC LIMIT 1", (cid,)).fetchone()
        return r["cluster_id"] if r else None

    def bundle(self, candidate_id: str) -> dict:
        cand = self._one(self.ix, "SELECT * FROM candidate WHERE candidate_id=?", (candidate_id,))
        if not cand:
            raise KeyError(candidate_id)
        compat = self._one(self.ix, "SELECT * FROM compatibility WHERE candidate_id=?", (candidate_id,))
        if compat:
            for f in ("harness", "requirements", "declared_compatibility"):
                if isinstance(compat.get(f), str):
                    try:
                        compat[f] = json.loads(compat[f])
                    except ValueError:
                        pass
        health = self._one(self.ix, "SELECT * FROM health WHERE candidate_id=?", (candidate_id,))
        if health:
            for f in ("scope", "flags"):
                if isinstance(health.get(f), str):
                    health[f] = json.loads(health[f])

        evaluation, freshness = self._evaluation(candidate_id, cand["content_hash"])
        verification = self._verification(candidate_id)
        return {"candidate": cand, "compatibility": compat, "health": health,
                "evaluation": evaluation, "evaluation_freshness": freshness,
                "verification": verification, "outcome_summary": self._outcomes(candidate_id),
                "primary_cluster": self._primary_cluster(candidate_id)}

    def _evaluation(self, cid, cur_hash):
        # local overlay (the user's own eval) wins over the published index.
        lr = self.local.execute("SELECT content_hash, json FROM local_evaluation WHERE candidate_id=?",
                                (cid,)).fetchall()
        rows = [(r["content_hash"], json.loads(r["json"])) for r in lr]
        if self._has(self.ix, "evaluation"):
            for r in self.ix.execute("SELECT content_hash, status FROM evaluation WHERE candidate_id=?", (cid,)):
                rows.append((r["content_hash"], None))  # presence marker for freshness
        if not rows:
            return None, "missing"
        for ch, rec in rows:
            if ch == cur_hash:
                if rec is None:   # from index: load full row
                    rec = self._index_eval(cid, ch)
                return rec, "fresh"
        return None, "stale"

    def _index_eval(self, cid, ch):
        if not self._has(self.ix, "evaluation"):
            return None
        r = self.ix.execute("SELECT * FROM evaluation WHERE candidate_id=? AND content_hash=?", (cid, ch)).fetchone()
        if not r:
            return None
        d = dict(r)
        for f in ("capabilities", "claims", "features", "limitations", "issue_resolution", "core_depends_on"):
            if isinstance(d.get(f), str):
                d[f] = json.loads(d[f])
        return d

    def _verification(self, cid):
        r = self.local.execute("SELECT json FROM local_verification WHERE candidate_id=? ORDER BY created_at DESC "
                               "LIMIT 1", (cid,)).fetchone()
        return json.loads(r["json"]) if r else None

    def _outcomes(self, cid):
        summ = {"yes": 0, "partial": 0, "no": 0}
        for r in self.local.execute("SELECT worked, COUNT(*) c FROM local_outcome WHERE candidate_id=? GROUP BY worked",
                                    (cid,)):
            summ[r["worked"]] = summ.get(r["worked"], 0) + r["c"]
        if self._has(self.ix, "outcome_reports"):
            for r in self.ix.execute("SELECT worked, COUNT(*) c FROM outcome_reports WHERE candidate_id=? "
                                     "GROUP BY worked", (cid,)):
                summ[r["worked"]] = summ.get(r["worked"], 0) + r["c"]
        return summ

    # ---- put -----------------------------------------------------------------
    def put(self, kind: str, record: dict) -> dict:
        if kind not in PUT_KINDS:
            return {"accepted": False, "reason": f"unknown kind '{kind}'"}
        cid = record.get("candidate_id")
        if not cid:
            return {"accepted": False, "reason": "missing candidate_id"}
        now = datetime.now(timezone.utc).isoformat()
        if kind == "evaluation":
            self.local.execute("INSERT OR REPLACE INTO local_evaluation (candidate_id, content_hash, json) "
                               "VALUES (?,?,?)", (cid, record.get("content_hash", ""), json.dumps(record)))
        elif kind == "verification":
            self.local.execute("INSERT INTO local_verification (candidate_id, content_hash, json, created_at) "
                               "VALUES (?,?,?,?)", (cid, record.get("content_hash", ""), json.dumps(record), now))
        else:
            self.local.execute("INSERT INTO local_outcome (candidate_id, worked, harness, note, contributor_id, "
                               "created_at) VALUES (?,?,?,?,?,?)",
                               (cid, record.get("worked", "partial"), record.get("harness"),
                                (record.get("note") or "")[:200], record.get("contributor_id"), now))
        self.local.commit()
        return {"accepted": True, "reason": ""}

    def close(self):
        self.ix.close()
        self.local.close()


def main(argv=None) -> int:
    # CLI used by the shipped skill's share step (steps/07-share.md).
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="store.py")
    ap.add_argument("cmd", choices=["put"])
    ap.add_argument("--kind", required=True, choices=sorted(PUT_KINDS))
    ap.add_argument("--file", required=True)
    ap.add_argument("--index")
    a = ap.parse_args(argv)
    record = json.loads(Path(a.file).read_text(encoding="utf-8"))
    store = get_store(index_path=a.index)
    try:
        res = store.put(a.kind, record)
    finally:
        store.close()
    print(json.dumps(res))
    return 0 if res.get("accepted") else 1


if __name__ == "__main__":
    raise SystemExit(main())
