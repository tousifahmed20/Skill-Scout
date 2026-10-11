"""Build the clustering + search artifacts into the pipeline DB (stage 05).

    python -m src.clustering                # embed -> cluster -> label -> search index (CI; needs the model)
    python -m src.clustering --search-only  # rebuild only the stdlib search index (no model)
    python -m src.clustering --stats

embed/cluster/label run in the GitHub Actions build (embed.py pulls the model).
The search index is stdlib-only and can be rebuilt on its own. Reads each
skill's text from the stage-02 checkout; cluster labels and (when present)
evaluation capabilities/actually_does become search fields.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from src.clustering import cluster as C
from src.clustering import search as S
from src.collector.membership import split_frontmatter
from src.db.core.db import REPO_ROOT, connect, migrate

CACHE_ROOT = REPO_ROOT / "data" / "cache" / "skills"


def _first_section(body: str, max_words: int = 300) -> str:
    out = []
    for line in body.splitlines():
        if out and line.lstrip().startswith("#"):
            break
        if line.lstrip().startswith("#"):
            continue
        out.append(line)
    return " ".join("\n".join(out).split()[:max_words])


def _skill_text(repo: str, skill_path: str, commit_sha: str) -> tuple[str, str, str] | None:
    sub = "" if skill_path == "." else skill_path
    md = CACHE_ROOT / repo.replace("/", "__") / commit_sha / sub / "SKILL.md"
    if not md.exists():
        return None
    fm_text, body = split_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
    fm = {}
    if fm_text:
        import yaml
        try:
            fm = yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            fm = {}
    name = fm.get("name", "") if isinstance(fm.get("name"), str) else ""
    desc = fm.get("description", "") if isinstance(fm.get("description"), str) else ""
    return name, desc, _first_section(body)


def _has_table(conn, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _load_docs(conn) -> dict[str, dict]:
    """candidate_id -> {name, description, first_section} from checkouts."""
    docs = {}
    for r in conn.execute("SELECT candidate_id, repo, skill_path, commit_sha FROM candidate WHERE status='active'"):
        t = _skill_text(r["repo"], r["skill_path"], r["commit_sha"])
        if t is None:
            continue
        docs[r["candidate_id"]] = {"candidate_id": r["candidate_id"],
                                   "name": t[0], "description": t[1], "first_section": t[2]}
    return docs


def _attach_labels(conn, docs: dict[str, dict]) -> None:
    if not _has_table(conn, "cluster"):
        return
    rows = conn.execute("SELECT cm.candidate_id, c.label FROM cluster_member cm "
                        "JOIN cluster c ON c.cluster_id = cm.cluster_id").fetchall()
    by_cand: dict[str, list[str]] = {}
    for cid, lab in rows:
        by_cand.setdefault(cid, []).append(lab)
    for cid, labs in by_cand.items():
        if cid in docs:
            docs[cid]["labels"] = sorted(set(labs))


def _attach_eval(conn, docs: dict[str, dict]) -> None:
    if not _has_table(conn, "evaluation"):
        return  # stage 06 not built / not run yet
    cols = {r[1] for r in conn.execute("PRAGMA table_info(evaluation)")}
    want = [c for c in ("capabilities", "actually_does") if c in cols]
    if not want:
        return
    for r in conn.execute(f"SELECT candidate_id, {','.join(want)} FROM evaluation"):
        d = docs.get(r["candidate_id"])
        if d:
            for c in want:
                d[c] = r[c]


def _build_search(conn) -> dict:
    docs = _load_docs(conn)
    _attach_labels(conn, docs)
    _attach_eval(conn, docs)
    backend = S.build_index(conn, list(docs.values()))
    return {"indexed": len(docs), "backend": backend}


def _embed_and_cluster(conn) -> dict:
    from src.clustering import embed as E
    docs = _load_docs(conn)
    if not docs:
        return {"embedded": 0}
    ids = list(docs)
    texts = [E.embed_text(docs[i]["name"], docs[i]["description"], docs[i]["first_section"]) for i in ids]
    vecs = E.embed(texts)
    conn.execute("DELETE FROM embedding")
    conn.executemany("INSERT INTO embedding (candidate_id, content_hash, model, dim, vector, text) "
                     "VALUES (?,?,?,?,?,?)",
                     [(ids[i], "", E.MODEL, E.DIM, json.dumps(vecs[i]), texts[i]) for i in range(len(ids))])
    clusters = C.cluster(list(zip(ids, vecs)))
    text_for_label = {i: f"{docs[i]['name']} {docs[i]['description']}" for i in ids}
    conn.execute("DELETE FROM cluster")
    conn.execute("DELETE FROM cluster_member")
    for cl in clusters:
        lab = C.label(cl["members"], text_for_label, cl["seed"])
        cur = conn.execute("INSERT INTO cluster (grp, label, seed_candidate_id, size) VALUES (?,?,?,?)",
                           (cl["group"], lab, cl["seed"], len(cl["members"])))
        cid = cur.lastrowid
        conn.executemany("INSERT INTO cluster_member (cluster_id, candidate_id, similarity) VALUES (?,?,?)",
                         [(cid, m, cl["similarity"][m]) for m in cl["members"]])
    conn.commit()
    return {"embedded": len(ids), "clusters": len(clusters)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m src.clustering")
    ap.add_argument("--search-only", action="store_true", help="rebuild only the search index (no model)")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args(argv)

    conn = connect()
    migrate(conn)
    if a.stats:
        print({"embeddings": conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0],
               "clusters": conn.execute("SELECT COUNT(*) FROM cluster").fetchone()[0],
               "search_docs": conn.execute("SELECT COUNT(*) FROM search_doc").fetchone()[0]
               if _has_table(conn, "search_doc") else 0})
        return 0

    result = {}
    if not a.search_only:
        result.update(_embed_and_cluster(conn))
    result.update(_build_search(conn))
    conn.commit()
    conn.close()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
