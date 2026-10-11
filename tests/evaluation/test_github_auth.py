"""Done-when: a signed-in GitHub CLI is used with no setup; Git's saved login
only after the user agrees; a planted token never appears in output."""
import github_auth as GA


def test_credential_order(monkeypatch):
    monkeypatch.setattr(GA, "_config", lambda: {})
    monkeypatch.setattr(GA, "_gh_cli_token", lambda: "GHCLI")
    monkeypatch.setattr(GA, "_git_credential_token", lambda cfg: "GIT")
    monkeypatch.delenv("SKILL_SCOUT_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # env var wins
    monkeypatch.setenv("SKILL_SCOUT_GITHUB_TOKEN", "ENVTOK")
    assert GA.get_token() == ("ENVTOK", "SKILL_SCOUT_GITHUB_TOKEN")
    # then config
    monkeypatch.delenv("SKILL_SCOUT_GITHUB_TOKEN")
    monkeypatch.setattr(GA, "_config", lambda: {"github_token": "CFGTOK"})
    assert GA.get_token() == ("CFGTOK", "config.json")
    # then gh cli (before git credential)
    monkeypatch.setattr(GA, "_config", lambda: {})
    assert GA.get_token() == ("GHCLI", "gh cli")


def test_git_credential_gated_by_consent(monkeypatch):
    calls = []
    monkeypatch.setattr(GA.subprocess, "run", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError))
    # allow_git_credentials not set -> git is never invoked
    assert GA._git_credential_token({}) is None
    assert GA._git_credential_token({"allow_git_credentials": False}) is None
    assert calls == []


def test_status_never_prints_token(monkeypatch, capsys):
    monkeypatch.setattr(GA, "get_token", lambda: ("SUPERSECRET-TOKEN", "config.json"))
    monkeypatch.setattr(GA, "_quota", lambda tok: "50/60 core requests left this hour")
    GA.cmd_status()
    out = capsys.readouterr().out
    assert "SUPERSECRET-TOKEN" not in out
    assert "authenticated (config.json)" in out


def test_api_get_refuses_non_github_host():
    import pytest
    with pytest.raises(ValueError):
        GA.api_get("https://evil.example.com/steal", token="T")
