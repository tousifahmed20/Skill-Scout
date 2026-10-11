"""Stage 09 assembly checks: host detection, SKILL.md portability, shipped-script
stdlib-only, cache-hit route, and an end-to-end answer record over a fixture
index (data plane — no model/harness). Golden accuracy (#1) and cross-harness
agreement (#2) need real harness runs and are deferred."""
import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "skill-scout"
SCRIPTS = SKILL_DIR / "scripts"
SPEC_FRONTMATTER = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
SIBLING_MODULES = {p.stem for p in SCRIPTS.glob("*.py")}


# ---- host detection ----------------------------------------------------------
def test_detect_harness():
    import detect_harness as D
    assert D.detect({"CLAUDECODE": "1"}) == "claude-code"
    assert D.detect({}) == "unknown"
    assert D.detect({"SOME_OTHER": "x"}) == "unknown"


# ---- SKILL.md portability ----------------------------------------------------
def test_skill_md_is_portable_and_short():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 100
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert fm, "missing frontmatter"
    keys = set(re.findall(r"^([A-Za-z_-]+):", fm.group(1), re.M))
    assert keys <= SPEC_FRONTMATTER, f"non-spec frontmatter keys: {keys - SPEC_FRONTMATTER}"
    name = re.search(r"^name:\s*(.+)$", fm.group(1), re.M).group(1).strip()
    assert name == SKILL_DIR.name
    assert len(re.search(r"^description:\s*(.+)$", fm.group(1), re.M).group(1)) <= 1024


# ---- shipped scripts are standard-library only -------------------------------
def test_shipped_scripts_stdlib_only():
    allowed = set(sys.stdlib_module_names) | SIBLING_MODULES
    for py in SCRIPTS.glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    assert n.name.split(".")[0] in allowed, f"{py.name}: non-stdlib import {n.name}"
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert (node.module or "").split(".")[0] in allowed, f"{py.name}: non-stdlib import {node.module}"


# ---- cache-hit route (Process step 5) ----------------------------------------
def test_cache_hit_route_only_loads_expected_steps():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d)\s+[^|]+\|([^|]+)\|([^|]+)\|", line)
        if m:
            rows[m.group(1)] = (m.group(2).strip(), m.group(3).strip().lower())
    # steps that must always load vs. load only conditionally
    for step in ("2", "4", "6"):
        assert "always" in rows[step][1], f"step {step} should always load"
    assert "only if" in rows["3"][1]       # evaluate: only on cache miss
    assert "only if" in rows["5"][1]       # verify: only on user agreement
    assert "only if" in rows["7"][1]       # share: only on new results


# ---- end-to-end answer record over a fixture index ---------------------------
def _fixture_index(tmp_path):
    from src.db.core.db import connect, migrate
    from src.clustering import search as search_mod
    profiles = json.loads((SKILL_DIR / "references" / "harness-profiles.json").read_text(encoding="utf-8"))
    db = tmp_path / "index.sqlite"
    conn = connect(db)
    migrate(conn)
    cid, ch = "o/good@s", "h1"
    conn.execute("INSERT INTO candidate (candidate_id, repo, skill_path, skill_name, description, distribution, "
                 "commit_sha, content_hash, files, status) VALUES (?,?,?,?,?,?,?,?,?, 'active')",
                 (cid, "o/good", "s", "good", "pdf report tool", "repo", "sha1", ch, "{}"))
    conn.execute("INSERT INTO health (candidate_id, content_hash, substantive_commits_90d, forks, releases, license, "
                 "scope, flags) VALUES (?,?,?,?,?,?, '{}', '[]')", (cid, ch, 15, 30, 2, "mit"))
    harness = {h["id"]: {"level": "compatible", "reasons": []} for h in profiles["harnesses"]}
    conn.execute("INSERT INTO compatibility (candidate_id, content_hash, harness, requirements, "
                 "declared_compatibility, declared_conflict) VALUES (?,?,?,?,?,0)",
                 (cid, ch, json.dumps(harness), "{}", None))
    claims = [{"claim": "c", "source": "skill_md", "importance": "core", "verdict": "supported",
               "evidence": "SKILL.md:1"}]
    conn.execute("INSERT INTO evaluation (candidate_id, content_hash, status, evaluator_model, actually_does, "
                 "capabilities, claims, features, limitations, issue_resolution, instruction_specificity, "
                 "example_realism, hype_score, core_depends_on, injection_detected, injection_detail, "
                 "evaluator_confidence) VALUES (?,?, 'active','m','builds a pdf report', ?,?,?,?,?,?,?,?,?,0,'',?)",
                 (cid, ch, json.dumps(["build pdf", "convert markdown"]), json.dumps(claims), json.dumps(["fast"]),
                  json.dumps([]), json.dumps({"threads_read": 0, "confirmed_fixed": 0, "closed_unresolved": 0}),
                  0.8, 0.7, 0.1, json.dumps([]), 0.8))
    conn.execute("INSERT INTO cluster (cluster_id, grp, label, seed_candidate_id, size) VALUES (1,NULL,'c',?,1)", (cid,))
    conn.execute("INSERT INTO cluster_member (cluster_id, candidate_id, similarity) VALUES (1,?,1.0)", (cid,))
    search_mod.build_index(conn, [{"candidate_id": cid, "name": "good", "description": "pdf report tool",
                                   "first_section": "convert markdown to pdf report"}])
    conn.commit()
    conn.close()
    return db


def test_end_to_end_answer_record(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILL_SCOUT_STORE", raising=False)
    import rank as R
    import store as store_mod
    db = _fixture_index(tmp_path)
    store = store_mod.get_store(index_path=db, local_path=tmp_path / "local.sqlite")
    task = {"task_text": "make a pdf report", "task_label": "pdf report",
            "capabilities": ["build pdf"], "search_terms": ["pdf", "report", "markdown", "convert"],
            "constraints": {"os": None, "free_only": False, "offline": False, "language": None},
            "host_harness": "claude-code"}
    out = R.rank(task, {"o/good@s": {"candidate_id": "o/good@s", "fit": "full", "missing": []}}, store)
    store.close()

    for key in ("task_label", "host_harness", "none_found", "picks", "display_harnesses",
                "harness_names", "verification_available"):
        assert key in out
    assert out["none_found"] is False and out["picks"]
    pick = out["picks"][0]
    for key in ("candidate_id", "skill_name", "install", "fit", "badge", "evidence_level",
                "actually_does", "compatibility", "sources", "claims_summary"):
        assert key in pick, f"pick missing {key}"
    # Done-when: every pick shows compatibility for the default-display harnesses.
    profiles = json.loads((SKILL_DIR / "references" / "harness-profiles.json").read_text(encoding="utf-8"))
    for hid in profiles["default_display"]:
        assert hid in pick["compatibility"], f"pick missing compatibility for {hid}"


# ---- default cache path auto-fetches the published release (offline stub) ----
def test_default_cache_path_triggers_release_download(tmp_path, monkeypatch):
    import gzip
    import io
    import urllib.request
    import store as store_mod
    src = _fixture_index(tmp_path)                       # a real migrated index
    payload = gzip.compress(src.read_bytes())
    cache = tmp_path / "cache" / "index.sqlite"          # pretend this is ~/.skill-scout/index.sqlite
    monkeypatch.setattr(store_mod, "_default_index", lambda: cache)
    monkeypatch.delenv("SKILL_SCOUT_INDEX_URL", raising=False)
    monkeypatch.delenv("SKILL_SCOUT_STORE", raising=False)
    seen = {}

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): self.close()

    def fake_urlopen(url, timeout=0):
        seen["url"] = url
        return _Resp(payload)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    store = store_mod.get_store(local_path=tmp_path / "local.sqlite")  # index_path=None -> default cache
    store.close()
    assert cache.exists()                                # download wrote the index
    assert seen["url"] == store_mod.DEFAULT_INDEX_URL     # from the baked-in release URL
    # and an explicit non-default path must NOT fetch:
    seen.clear()
    store2 = store_mod.get_store(index_path=src, local_path=tmp_path / "local2.sqlite")
    store2.close()
    assert "url" not in seen
