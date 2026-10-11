#!/usr/bin/env python3
"""Find the user's GitHub login for read-only API calls (stage 06). Standard
library only. The token is sent only to api.github.com and is never printed,
logged, cached, or stored anywhere else (github-access.md).

Credential order (first that works): SKILL_SCOUT_GITHUB_TOKEN env; github_token
in ~/.skill-scout/config.json; GH_TOKEN; GITHUB_TOKEN; `gh auth token`; Git's
saved login via `git credential fill` (only when config allow_git_credentials is
true); else anonymous (60 req/h per IP).

    python github_auth.py status   # authenticated (<source>) | anonymous + quota
    python github_auth.py init     # create config.json with an empty github_token
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
_CONFIG_ENV = "SKILL_SCOUT_CONFIG"


def config_path() -> Path:
    return Path(os.environ.get(_CONFIG_ENV) or (Path.home() / ".skill-scout" / "config.json"))


def _config() -> dict:
    p = config_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
    return {}


def _gh_cli_token() -> str | None:
    try:
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    tok = r.stdout.strip()
    return tok or None


def _git_credential_token(cfg: dict) -> str | None:
    if not cfg.get("allow_git_credentials"):      # source 5 only after the user agrees once
        return None
    try:
        r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in r.stdout.splitlines():
        if line.startswith("password="):
            return line[len("password="):].strip() or None
    return None


def get_token() -> tuple[str | None, str]:
    """(token, source). source is 'anonymous' when nothing is found. The token
    is returned for use, never logged by callers."""
    cfg = _config()
    env = os.environ
    if env.get("SKILL_SCOUT_GITHUB_TOKEN"):
        return env["SKILL_SCOUT_GITHUB_TOKEN"], "SKILL_SCOUT_GITHUB_TOKEN"
    if cfg.get("github_token"):
        return cfg["github_token"], "config.json"
    for name in ("GH_TOKEN", "GITHUB_TOKEN"):
        if env.get(name):
            return env[name], name
    tok = _gh_cli_token()
    if tok:
        return tok, "gh cli"
    tok = _git_credential_token(cfg)
    if tok:
        return tok, "git credential"
    return None, "anonymous"


def api_get(path: str, token: str | None = None):
    """Read-only GET to api.github.com only. Returns (json, headers)."""
    if path.startswith(("http://", "https://")):
        if not path.startswith(API + "/") and path != API:   # never send the token off api.github.com
            raise ValueError("refusing to call a non-GitHub host")
    else:
        path = API + (path if path.startswith("/") else "/" + path)
    headers = {"User-Agent": "skill-scout", "Accept": "application/vnd.github+json"}
    if token is None:
        token, _ = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(path, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), dict(r.headers)


def _quota(token: str | None) -> str:
    try:
        data, _ = api_get("/rate_limit", token)
        core = data.get("resources", {}).get("core", {})
        return f"{core.get('remaining', '?')}/{core.get('limit', '?')} core requests left this hour"
    except urllib.error.URLError:
        return "quota unknown (offline)"


def cmd_status() -> int:
    token, source = get_token()
    if token:
        print(f"authenticated ({source}) — {_quota(token)}")   # token itself never printed
    else:
        print(f"anonymous — {_quota(None)}")
    return 0


def cmd_init() -> int:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(json.dumps({"github_token": "", "allow_git_credentials": False}, indent=2) + "\n",
                     encoding="utf-8")
        try:
            os.chmod(p, 0o600)                      # user-only where the OS supports it
        except OSError:
            pass
    print(str(p))
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "status"
    if cmd == "status":
        return cmd_status()
    if cmd == "init":
        return cmd_init()
    print("usage: github_auth.py [status|init]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
