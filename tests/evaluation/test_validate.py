"""Done-when: a fabricated evidence ref is rejected by the validator; a valid
record passes. Also schema checks."""
import copy

import validate_evaluation as V


def _checkout(tmp_path):
    (tmp_path / "SKILL.md").write_text("\n".join(f"line {i}" for i in range(1, 21)), encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("a=1\nb=2\n", encoding="utf-8")
    return tmp_path


VALID = {
    "candidate_id": "o/r@s", "content_hash": "h", "commit_sha": "abc", "evaluator_model": "m",
    "actually_does": "Does a thing.", "capabilities": ["do a", "do b"],
    "claims": [{"claim": "does a", "source": "skill_md", "importance": "core",
                "verdict": "supported", "evidence": "SKILL.md:5"}],
    "features": [], "limitations": [{"text": "no windows", "evidence": "scripts/run.py:1"}],
    "issue_resolution": {"threads_read": 0, "confirmed_fixed": 0, "closed_unresolved": 0},
    "instruction_specificity": 0.7, "example_realism": 0.5, "hype_score": 0.1,
    "core_depends_on": [], "injection_detected": False, "injection_detail": "",
    "evaluator_confidence": 0.8,
}


def test_valid_record_passes(tmp_path):
    assert V.validate(copy.deepcopy(VALID), _checkout(tmp_path)) == []


def test_fabricated_path_rejected(tmp_path):
    r = copy.deepcopy(VALID)
    r["claims"][0]["evidence"] = "does-not-exist.md:3"
    errs = V.validate(r, _checkout(tmp_path))
    assert any("file not found" in e for e in errs)


def test_line_out_of_range_rejected(tmp_path):
    r = copy.deepcopy(VALID)
    r["claims"][0]["evidence"] = "SKILL.md:9999"
    errs = V.validate(r, _checkout(tmp_path))
    assert any("out of range" in e for e in errs)


def test_bad_format_rejected(tmp_path):
    r = copy.deepcopy(VALID)
    r["claims"][0]["evidence"] = "just some prose"
    errs = V.validate(r, _checkout(tmp_path))
    assert any("path:line" in e for e in errs)


def test_schema_errors():
    r = copy.deepcopy(VALID)
    r["hype_score"] = 2.0                 # out of 0..1
    r["capabilities"] = ["only one"]      # needs 2-8
    r["claims"] = []                      # non-empty required
    errs = V.validate(r, None)
    assert any("hype_score" in e for e in errs)
    assert any("capabilities" in e for e in errs)
    assert any("claims" in e for e in errs)


def test_issue_ref_ok_without_checkout():
    r = copy.deepcopy(VALID)
    r["claims"][0]["evidence"] = "issue #42"
    assert V.validate(r, None) == []
