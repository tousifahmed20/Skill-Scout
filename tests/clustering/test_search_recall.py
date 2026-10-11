"""Done-when: recall + stdlib-only search, on both backends.

Builds the search index from the 40 cached golden docs and, for each golden
task, runs search() with model-written terms (derived from the task sentence).
Every acceptable pick must appear in search(terms, 30). Runs on FTS5 and on the
forced pure-Python BM25 fallback so the stdlib path is exercised too."""
import json
import sqlite3
from pathlib import Path

import pytest

from src.clustering import search as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DOCS = json.loads((HERE / "golden_docs.json").read_text(encoding="utf-8"))
TERMS = json.loads((HERE / "task_terms.json").read_text(encoding="utf-8"))["terms"]
TASKS = json.loads((ROOT / "data" / "golden-set" / "tasks.json").read_text(encoding="utf-8"))
INDEXED = {d["candidate_id"] for d in DOCS}


def _index(fallback: bool) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    backend = S.build_index(conn, DOCS)
    if fallback:                       # drop FTS5 so search() uses pure-Python BM25
        conn.execute("DROP TABLE IF EXISTS search_fts")
        conn.commit()
    else:
        assert backend == "fts5", "expected FTS5 in this environment"
    return conn


def test_all_picks_are_indexed():
    # Guard: a recall miss should mean 'not recalled', never 'not in the index'.
    for t in TASKS:
        for pick in t["acceptable_picks"]:
            assert pick in INDEXED, f"acceptable pick not in golden docs: {pick}"
        assert t["task"] in TERMS, f"no model terms for task: {t['task']}"


@pytest.mark.parametrize("fallback", [False, True], ids=["fts5", "python-bm25"])
def test_recall_at_30(fallback):
    conn = _index(fallback)
    misses = []
    for t in TASKS:
        q = TERMS[t["task"]]
        got = set(S.search(conn, q["search_terms"], 30, q["capabilities"]))
        for pick in t["acceptable_picks"]:
            if pick not in got:
                misses.append((t["task"], pick))
    total = sum(len(t["acceptable_picks"]) for t in TASKS)
    rate = 1 - len(misses) / total
    assert rate >= 0.95, f"recall {rate:.2%} (<95%); misses: {misses}"


def test_search_is_stdlib_only():
    # search.py must import nothing outside the standard library.
    import ast
    src = (ROOT / "src" / "clustering" / "search.py").read_text(encoding="utf-8")
    stdlib = {"__future__", "math", "re", "sqlite3"}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            for n in node.names:
                assert n.name.split(".")[0] in stdlib, f"non-stdlib import: {n.name}"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] in stdlib, f"non-stdlib import: {node.module}"
