"""Build a fixture index DB (lower-stage tables + search index) and expose a
Store over it, so ranking can be tested without a real pipeline run."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "skill-scout" / "scripts"
for p in (str(SCRIPTS), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from src.db.core.db import connect, migrate          # noqa: E402
from src.clustering import search as search_mod        # noqa: E402


def _default_health(cid, ch):
    return {"candidate_id": cid, "content_hash": ch, "substantive_commits_90d": 0, "independent_contributors": 0,
            "independent_issue_reports": 0, "linked_fix_closures": 0, "closed_without_fix": 0, "stars": 0,
            "star_velocity_7d": 0, "stargazer_quality": None, "installs": None, "forks": 0, "releases": 0,
            "license": None, "archived": 0, "author_track_record": 0.0, "early_organic_traction": 0.0,
            "scope": {}, "flags": []}


def _eval(cid, ch, *, hype_score=0.1, instruction_specificity=0.7, example_realism=0.6,
          core_supported=2, core_unsupported=0, inj=False, depends=None):
    claims = [{"claim": f"core{i}", "source": "skill_md", "importance": "core", "verdict": "supported",
               "evidence": "SKILL.md:1"} for i in range(core_supported)]
    claims += [{"claim": f"badcore{i}", "source": "skill_md", "importance": "core", "verdict": "unsupported",
                "evidence": "SKILL.md:1"} for i in range(core_unsupported)]
    return {"candidate_id": cid, "content_hash": ch, "status": "active", "evaluator_model": "m",
            "actually_does": "does the thing", "capabilities": json.dumps(["do a", "do b"]),
            "claims": json.dumps(claims), "features": json.dumps(["f"]), "limitations": json.dumps([]),
            "issue_resolution": json.dumps({"threads_read": 0, "confirmed_fixed": 0, "closed_unresolved": 0}),
            "instruction_specificity": instruction_specificity, "example_realism": example_realism,
            "hype_score": hype_score, "core_depends_on": json.dumps(depends or []),
            "injection_detected": 1 if inj else 0, "injection_detail": "", "evaluator_confidence": 0.8}


def make_index(tmp_path, specs):
    """specs: list of dicts: {id, text, first_seen, health{}, eval{}|None, compat_levels{host:level}}."""
    db = tmp_path / "index.sqlite"
    conn = connect(db)
    migrate(conn)
    docs = []
    for sp in specs:
        cid = sp["id"]
        ch = sp.get("content_hash", "h_" + cid.replace("/", "_").replace("@", "_"))
        repo, skill_path = cid.split("@", 1)
        conn.execute("INSERT INTO candidate (candidate_id, repo, skill_path, skill_name, description, distribution, "
                     "first_seen, commit_sha, content_hash, files, status) VALUES (?,?,?,?,?,?,?,?,?,?, 'active')",
                     (cid, repo, skill_path, skill_path.rsplit("/", 1)[-1], sp.get("text", ""),
                      sp.get("distribution", "repo"), sp.get("first_seen"), "sha" + cid[-4:], ch,
                      json.dumps(sp.get("files", {})) ))
        h = {**_default_health(cid, ch), **sp.get("health", {})}
        h["scope"] = json.dumps(h["scope"]); h["flags"] = json.dumps(h["flags"])
        cols = ",".join(h); conn.execute(f"INSERT INTO health ({cols}) VALUES ({','.join('?' for _ in h)})", list(h.values()))
        harness = sp.get("compat", {"harness": {}, "requirements": {}})
        conn.execute("INSERT INTO compatibility (candidate_id, content_hash, harness, requirements, "
                     "declared_compatibility, declared_conflict) VALUES (?,?,?,?,?,0)",
                     (cid, ch, json.dumps(harness.get("harness", {})), json.dumps(harness.get("requirements", {})), None))
        ev_spec = sp.get("eval")
        if ev_spec is not None:
            ev = _eval(cid, ch, **ev_spec)          # ev_spec holds _eval knobs, not columns
            conn.execute(f"INSERT INTO evaluation ({','.join(ev)}) VALUES ({','.join('?' for _ in ev)})", list(ev.values()))
        # one shared cluster so percentiles compare the fixtures
        conn.execute("INSERT INTO cluster_member (cluster_id, candidate_id, similarity) VALUES (1, ?, 1.0)", (cid,))
        docs.append({"candidate_id": cid, "name": sp.get("text", ""), "description": sp.get("text", ""),
                     "first_section": sp.get("text", "")})
    conn.execute("INSERT INTO cluster (cluster_id, grp, label, seed_candidate_id, size) VALUES (1, NULL, 'c', ?, ?)",
                 (specs[0]["id"], len(specs)))
    search_mod.build_index(conn, docs)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def store_factory(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILL_SCOUT_STORE", raising=False)
    import store as store_mod

    def factory(specs):
        db = make_index(tmp_path, specs)
        return store_mod.get_store(index_path=db, local_path=tmp_path / "local.sqlite")
    return factory
