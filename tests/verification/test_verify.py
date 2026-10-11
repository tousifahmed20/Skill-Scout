"""Stage 07 deterministic gates: runner gating, cost estimate, scripts -> second
confirmation (#3), temp-folder-only + cleanup (#4), record validation. The real
with/without run (#1 delta direction; #2 empirical ±30%) happens on the user's
machine and is not run here."""
import json
import tempfile
from pathlib import Path

import pytest

import verify as V

LOC = {"candidate_id": "o/r@s", "repo": "o/r", "skill_path": "s", "commit_sha": "sha"}


@pytest.fixture(autouse=True)
def _isolate_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "SESSIONS", tmp_path / "verify_sessions.json")


# ---- runner gating -----------------------------------------------------------
def test_runner_known_and_unknown():
    assert V._runner("claude-code")              # verified in harness-profiles.json
    assert V._runner("antigravity")              # resolved by stage 07 (agy -p)
    with pytest.raises(KeyError):
        V._runner("does-not-exist")


def test_estimate_refuses_without_verified_runner(monkeypatch, capsys):
    monkeypatch.setattr(V, "_runner", lambda h: None)
    assert V.cmd_estimate("o/r@s", "antigravity", Path("x.sqlite")) == 3
    assert "not offered" in capsys.readouterr().err


# ---- cost estimate -----------------------------------------------------------
def test_estimate_scales_with_skill_size():
    small = V.estimate_tokens("x" * 400)         # ~100 tokens
    big = V.estimate_tokens("x" * 40000)         # ~10k tokens
    assert big > small > 0


def test_estimate_within_30pct_of_modeled_actual():
    # Estimate uses a fixed output budget; a real run's output varies. Check the
    # estimate stays within +/-30% of a modeled actual as output swings +/-40%.
    skill = "s" * 8000                           # ~2000-token skill
    est = V.estimate_tokens(skill)
    skill_tok = len(skill) // 4
    for factor in (0.6, 1.0, 1.4):               # actual output per call vs the 700 budget
        out = V.OUTPUT_TOKENS * factor
        per_task = (V.TASK_PROMPT_TOKENS + out
                    + V.TASK_PROMPT_TOKENS + skill_tok + out
                    + 2 * out + V.CRITERIA_TOKENS + V.JUDGE_OUTPUT_TOKENS * factor)
        actual = V.TASKS * per_task
        assert abs(est - actual) / actual <= 0.30, (factor, est, actual)


# ---- setup: scripts (#3) + temp-folder-only (#4) -----------------------------
def _patch_download(monkeypatch, files):
    monkeypatch.setattr(V, "resolve", lambda cid, db: LOC)
    monkeypatch.setattr(V, "_folder_files", lambda loc, token: list(files))
    monkeypatch.setattr(V.github_auth, "get_token", lambda: (None, "anonymous"))
    monkeypatch.setattr(V, "_raw", lambda repo, sha, path: b"content\n")


def test_setup_flags_scripts_for_second_confirmation(monkeypatch, capsys):
    _patch_download(monkeypatch, ["SKILL.md", "scripts/run.py", "references/guide.md"])
    assert V.cmd_setup("o/r@s", Path("x.sqlite")) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["scripts_present"] is True
    assert "scripts/run.py" in out["scripts"]
    assert "second_confirmation_required" in out
    Path(out["temp_dir"]).exists() and __import__("shutil").rmtree(out["temp_dir"], ignore_errors=True)


def test_setup_no_scripts_no_second_confirmation(monkeypatch, capsys):
    _patch_download(monkeypatch, ["SKILL.md", "references/guide.md"])
    V.cmd_setup("o/r@s", Path("x.sqlite"))
    out = json.loads(capsys.readouterr().out)
    assert out["scripts_present"] is False and "second_confirmation_required" not in out
    __import__("shutil").rmtree(out["temp_dir"], ignore_errors=True)


def test_setup_writes_only_inside_temp_and_finish_cleans_up(monkeypatch, capsys):
    _patch_download(monkeypatch, ["SKILL.md", "scripts/run.py"])
    V.cmd_setup("o/r@s", Path("x.sqlite"))
    temp_dir = Path(json.loads(capsys.readouterr().out)["temp_dir"])
    assert temp_dir.is_dir() and str(temp_dir).startswith(tempfile.gettempdir())
    written = [p for p in temp_dir.rglob("*") if p.is_file()]
    assert written and all(str(p).startswith(str(temp_dir)) for p in written)

    rec = {"candidate_id": "o/r@s", "harness": "claude-code", "with_score": 0.8,
           "without_score": 0.5, "delta": 0.3, "verdict": "gain", "status": "single"}
    rpath = temp_dir.parent / "rec.json"
    rpath.write_text(json.dumps(rec), encoding="utf-8")
    assert V.cmd_finish(str(rpath)) == 0
    assert not temp_dir.exists()                 # #4: nothing left behind
    rpath.unlink()


def test_finish_never_deletes_a_non_temp_path(monkeypatch, tmp_path, capsys):
    # A session pointing outside the system temp (e.g. a user folder) is left alone.
    user_dir = tmp_path / "my-project"
    user_dir.mkdir()
    V._save_sessions({"o/r@s": str(user_dir)})
    rec = {"candidate_id": "o/r@s", "harness": "claude-code", "with_score": 0.5,
           "without_score": 0.5, "delta": 0.0, "verdict": "no_measurable_gain"}
    rpath = tmp_path / "rec.json"
    rpath.write_text(json.dumps(rec), encoding="utf-8")
    V.cmd_finish(str(rpath))
    assert user_dir.exists()                     # safety: user path not deleted
    assert json.loads(capsys.readouterr().out)["temp_dir_deleted"] is False


# ---- record validation -------------------------------------------------------
def test_validate_record_verdict_matches_delta():
    base = {"candidate_id": "c", "harness": "h", "with_score": 0.7, "without_score": 0.5,
            "delta": 0.2, "verdict": "gain"}
    assert V.validate_record(base) == []
    assert any("verdict" in e for e in V.validate_record({**base, "verdict": "worse"}))
    assert any("delta" in e for e in V.validate_record({**base, "delta": 0.99}))
    assert any("missing" in e for e in V.validate_record({"candidate_id": "c"}))
