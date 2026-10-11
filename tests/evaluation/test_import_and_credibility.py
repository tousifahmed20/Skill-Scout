"""Done-when: the build imports every committed seed; a skill whose content
changed shows stale. Plus the provisional credibility formula ranks a good
profile above a hype profile (stage 08 owns the canonical version)."""
import json

from src.db.core.db import connect, migrate
from src.evaluation import __main__ as M
from src.evaluation.credibility import credibility


def _candidate(conn, cid, content_hash):
    conn.execute(
        "INSERT INTO candidate (candidate_id, repo, skill_path, skill_name, distribution, "
        "content_hash, status) VALUES (?,?,?,?,?,?, 'active')",
        (cid, cid.split("@")[0], cid.split("@")[1], "s", "repo", content_hash))


def _seed_file(d, cid, content_hash):
    rec = {"candidate_id": cid, "content_hash": content_hash, "commit_sha": "x",
           "evaluator_model": "m", "actually_does": "", "capabilities": ["a", "b"],
           "claims": [], "features": [], "limitations": [], "issue_resolution": {},
           "instruction_specificity": 0.5, "example_realism": 0.5, "hype_score": 0.2,
           "core_depends_on": [], "injection_detected": False, "injection_detail": "",
           "evaluator_confidence": 0.7}
    (d / f"{cid.replace('/', '__').replace('@', '__')}.json").write_text(json.dumps(rec), encoding="utf-8")


def test_import_marks_active_and_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "SEED_DIR", tmp_path)
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    _candidate(conn, "o/r@fresh", "h1")      # eval hash matches -> active
    _candidate(conn, "o/r@changed", "h2new")  # candidate moved on -> eval is stale
    conn.commit()
    _seed_file(tmp_path, "o/r@fresh", "h1")
    _seed_file(tmp_path, "o/r@changed", "h2old")

    res = M.import_seeds(conn)
    assert res["imported"] == 2
    rows = {r["candidate_id"]: r["status"] for r in conn.execute("SELECT candidate_id, status FROM evaluation")}
    assert rows == {"o/r@fresh": "active", "o/r@changed": "stale"}


GOOD = {"hype_score": 0.1, "instruction_specificity": 0.9, "example_realism": 0.8,
        "issue_resolution": {"confirmed_fixed": 3, "closed_unresolved": 0},
        "claims": [{"importance": "core", "verdict": "supported"},
                   {"importance": "core", "verdict": "supported"}],
        "injection_detected": False}
HYPE = {"hype_score": 0.9, "instruction_specificity": 0.2, "example_realism": 0.1,
        "issue_resolution": {"confirmed_fixed": 0, "closed_unresolved": 4},
        "claims": [{"importance": "core", "verdict": "unsupported"},
                   {"importance": "core", "verdict": "unsupported"}],
        "injection_detected": False}


def test_credibility_ranks_good_above_hype():
    assert credibility(GOOD) > credibility(HYPE)
    assert credibility(GOOD) >= 0.7 and credibility(HYPE) <= 0.4


def test_injection_zeroes_credibility():
    assert credibility({**GOOD, "injection_detected": True}) == 0.0
