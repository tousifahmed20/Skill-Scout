"""Done-when: input per candidate stays within the evidence budget; and with no
credentials a 5-candidate query stays within the anonymous API limit (<=3
calls/candidate => <=15)."""
import fetch_evidence as FE


def _checkout(tmp_path, skill_lines=50, script_lines=40):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\n" + "\n".join(f"step {i}" for i in range(skill_lines)),
        encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run.py").write_text("\n".join(f"x{i}=1" for i in range(script_lines)), encoding="utf-8")
    (tmp_path / "README.md").write_text("# R\n" + "\n".join(f"r{i}" for i in range(100)), encoding="utf-8")
    return tmp_path


def test_offline_build_within_cap_and_no_api_calls(tmp_path):
    FE.api_calls = 0
    loc = {"candidate_id": "o/r@s", "repo": "o/r", "skill_path": "s", "commit_sha": "local"}
    text, meta = FE.build(loc, token=None, checkout=_checkout(tmp_path))
    assert meta["approx_tokens"] <= FE.TOKEN_CAP
    assert meta["api_calls"] == 0                 # checkout path hits no network
    assert "SKILL.md" in text and "<<<UNTRUSTED" in text


def test_hard_cap_drops_low_priority_but_keeps_skill_md(tmp_path):
    # oversized scripts + README force cutting; SKILL.md must survive.
    big = _checkout(tmp_path, skill_lines=30, script_lines=20000)
    FE.api_calls = 0
    text, meta = FE.build({"candidate_id": "o/r@s", "repo": "o/r", "skill_path": "s", "commit_sha": "local"},
                          token=None, checkout=big)
    assert meta["approx_tokens"] <= FE.TOKEN_CAP
    assert 'file="s/SKILL.md"' in text            # never dropped


def test_api_calls_within_anonymous_limit_for_5_candidates(monkeypatch):
    # No checkout -> uses the API for tree + issues only; files come from the CDN.
    monkeypatch.setattr(FE, "_raw", lambda repo, sha, path: "line\nline\n" if path.endswith("SKILL.md") else None)

    def fake_api(path, token):
        if "git/trees" in path:
            return {"tree": [{"type": "blob", "path": "s/SKILL.md"}]}, {}
        if "/issues" in path:
            return [], {}
        return {}, {}
    monkeypatch.setattr(FE.github_auth, "api_get", fake_api)

    FE.api_calls = 0
    for i in range(5):
        FE.build({"candidate_id": f"o/r@s{i}", "repo": "o/r", "skill_path": "s", "commit_sha": "sha"},
                 token=None, checkout=None)
    assert FE.api_calls <= 15, FE.api_calls           # <= 3 per candidate
