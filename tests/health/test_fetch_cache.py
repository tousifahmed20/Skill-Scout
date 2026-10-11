"""The 1,000-candidate budget (Done-when #2) relies on repo-level GitHub data
being fetched once per repo, not once per skill. Lock that: two skills in one
repo share every repo-level call; only the skill-level commit call repeats."""
from datetime import datetime, timezone

from src.health import fetch


def test_repo_level_calls_shared_across_skills_in_one_repo(monkeypatch):
    fetch.clear_caches()
    calls = {}

    def counter(name, ret):
        def f(*a, **k):
            calls[name] = calls.get(name, 0) + 1
            return ret
        return f

    monkeypatch.setattr(fetch, "_repo_meta", counter("repo_meta", {"owner": "acme", "stars": 3}))
    monkeypatch.setattr(fetch, "_contributors", counter("contributors", []))
    monkeypatch.setattr(fetch, "_stargazers", counter("stargazers", []))
    monkeypatch.setattr(fetch, "_forks", counter("forks", []))
    monkeypatch.setattr(fetch, "_issues_raw", counter("issues", []))
    monkeypatch.setattr(fetch, "_enrich_user", counter("enrich", {"login": "acme"}))
    monkeypatch.setattr(fetch, "_commits", counter("commits", []))

    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    common = {"repo": "acme/pack", "distribution": "collection", "content_hash": "h"}
    fetch.build_raw({**common, "candidate_id": "acme/pack@a", "skill_path": "a", "skill_name": "a"}, now)
    fetch.build_raw({**common, "candidate_id": "acme/pack@b", "skill_path": "b", "skill_name": "b"}, now)

    for repo_level in ("repo_meta", "contributors", "stargazers", "forks", "issues", "enrich"):
        assert calls[repo_level] == 1, f"{repo_level} fetched {calls[repo_level]}x (should be 1 for the repo)"
    assert calls["commits"] == 2, "commits are skill-level and should run per skill"
