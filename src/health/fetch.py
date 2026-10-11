"""Fetch the GitHub facts compute.py needs, into one `raw` dict per candidate.

Reuses the stage-02 client (`src.collector.discovery`): its authenticated
`_api` (rate-limit backoff + RateLimited), token, and API base. Only the
stargazer endpoint needs a non-default Accept (star+json, for `starred_at`), so
this module adds one small GET for it rather than touching the stage-02 file.

Budget (CLAUDE.md: within GitHub rate limits for 1,000 candidates): calls per
candidate are capped — repo(1) + releases(1) + contributors(1) + a bounded
user-enrich + commits(1) + capped commit-stats + issues(1) + stargazers(<=3) +
forks(1). On a far-off rate-limit reset `discovery.RateLimited` propagates so
the run stops cleanly and resumes by staleness next time. No execution of skill
code; no LLM.
"""
from __future__ import annotations
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from src.collector import discovery
from src.collector.discovery import API, _api, _request

CONTRIB_CAP = 25
COMMIT_STATS_CAP = 15
ISSUE_CAP = 100
STAR_PER_PAGE = 100
FORK_CAP = 50
COMMIT_WINDOW_DAYS = 90

# ponytail: per-run caches. A collection repo holds many skills; its repo-level
# data (meta/contributors/stargazers/forks/issues) is identical for all of them,
# so fetch it once per repo. Keeps 1,000 clustered candidates inside the budget.
_user_cache: dict[str, dict] = {}
_repo_cache: dict[str, dict] = {}


def clear_caches() -> None:
    _user_cache.clear()
    _repo_cache.clear()


def _last_page(headers: dict) -> int:
    m = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', headers.get("Link", ""))
    return int(m.group(1)) if m else 1


def _star_get(url: str, _retries: int = 3):
    """GET the stargazers endpoint with the star+json Accept (for `starred_at`).
    Mirrors discovery._api's rate-limit handling for the one non-default Accept."""
    import json
    import time
    try:
        with urllib.request.urlopen(_request(url, accept="application/vnd.github.star+json"), timeout=30) as r:
            return json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            reset = float(e.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = reset - time.time()
            if wait > discovery.MAX_BACKOFF_SECONDS:
                raise discovery.RateLimited(reset) from None
            time.sleep(max(1.0, wait) + 1)
            if _retries > 0:
                return _star_get(url, _retries - 1)
        raise


def _enrich_user(login: str) -> dict:
    if not login:
        return {}
    key = login.lower()
    if key not in _user_cache:
        try:
            u, _ = _api(f"{API}/users/{urllib.parse.quote(login)}")
            _user_cache[key] = {"login": login, "id": u.get("id"), "type": u.get("type"),
                                "created_at": u.get("created_at"), "public_repos": u.get("public_repos")}
        except urllib.error.HTTPError:
            _user_cache[key] = {"login": login}
    return dict(_user_cache[key])


def _repo_meta(repo: str) -> dict:
    meta, _ = _api(f"{API}/repos/{repo}")
    lic = (meta.get("license") or {}).get("spdx_id") or (meta.get("license") or {}).get("key")
    if lic in ("NOASSERTION", None, ""):
        lic = (meta.get("license") or {}).get("key") or None
    rel, h = _api(f"{API}/repos/{repo}/releases?per_page=1")
    releases = _last_page(h) if rel else 0
    return {"stars": meta.get("stargazers_count", 0), "forks": meta.get("forks_count", 0),
            "archived": bool(meta.get("archived")), "license": lic,
            "pushed_at": meta.get("pushed_at"), "last_commit": meta.get("pushed_at"),
            "releases": releases, "owner": (meta.get("owner") or {}).get("login", "")}


def _contributors(repo: str) -> list[dict]:
    try:
        data, _ = _api(f"{API}/repos/{repo}/contributors?per_page={CONTRIB_CAP}&anon=0")
    except urllib.error.HTTPError:
        return []
    out = []
    for c in (data or [])[:CONTRIB_CAP]:
        if c.get("type") == "Anonymous":
            continue
        out.append(_enrich_user(c.get("login", "")))
    return out


def _commits(repo: str, skill_path: str, now: datetime) -> list[dict]:
    since = (now - timedelta(days=COMMIT_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    q = f"{API}/repos/{repo}/commits?per_page=100&since={since}"
    if skill_path and skill_path != ".":
        q += f"&path={urllib.parse.quote(skill_path)}"
    try:
        lst, _ = _api(q)
    except urllib.error.HTTPError:
        return []
    prefix = "" if skill_path in ("", ".") else skill_path.rstrip("/") + "/"
    out = []
    for i, c in enumerate(lst or []):
        row = {"sha": c.get("sha"), "date": (c.get("commit") or {}).get("committer", {}).get("date"),
               "login": (c.get("author") or {}).get("login")}
        if i < COMMIT_STATS_CAP:        # per-commit stats cost one call each; cap it
            try:
                full, _ = _api(f"{API}/repos/{repo}/commits/{c['sha']}")
                row["additions"] = (full.get("stats") or {}).get("additions", 0)
                row["deletions"] = (full.get("stats") or {}).get("deletions", 0)
                allfiles = [f.get("filename", "") for f in full.get("files") or []]
                row["files"] = [f[len(prefix):] for f in allfiles if not prefix or f.startswith(prefix)]
            except urllib.error.HTTPError:
                pass
        out.append(row)
    return out


def _mentions(it: dict, skill_name: str, skill_path: str) -> bool:
    text = f"{it.get('title', '')}\n{it.get('body', '') or ''}".lower()
    return (skill_name and skill_name.lower() in text) or (skill_path and skill_path.lower() in text)


def _issues_raw(repo: str) -> list[dict]:
    """Repo-level issue list (non-PR), unfiltered. build_raw filters per skill."""
    try:
        lst, _ = _api(f"{API}/repos/{repo}/issues?state=all&per_page={ISSUE_CAP}")
    except urllib.error.HTTPError:
        return []
    out = []
    for it in lst or []:
        if "pull_request" in it:        # issues endpoint also returns PRs
            continue
        out.append({"number": it.get("number"), "login": (it.get("user") or {}).get("login"),
                    "author_association": it.get("author_association"),
                    "created_at": it.get("created_at"), "closed_at": it.get("closed_at"),
                    "state_reason": it.get("state_reason"),
                    "title": it.get("title", ""), "body": it.get("body", "")})
    return out


def _repo_bundle(repo: str) -> dict:
    """Repo-level facts, fetched once per repo per run (cached)."""
    if repo not in _repo_cache:
        meta = _repo_meta(repo)
        _repo_cache[repo] = {"meta": meta, "contributors": _contributors(repo),
                             "stargazers": _stargazers(repo), "forks": _forks(repo),
                             "issues": _issues_raw(repo),
                             "author": _enrich_user(meta.get("owner") or repo.split("/")[0])}
    return _repo_cache[repo]


def _stargazers(repo: str) -> list[dict]:
    url = f"{API}/repos/{repo}/stargazers?per_page={STAR_PER_PAGE}&page=1"
    try:
        page1, h = _star_get(url)
    except urllib.error.HTTPError:
        return []
    last = _last_page(h)
    pages = {1: page1}
    for p in {last, last - 1}:          # newest stars live on the last pages
        if p > 1 and p not in pages:
            try:
                pages[p], _ = _star_get(f"{API}/repos/{repo}/stargazers?per_page={STAR_PER_PAGE}&page={p}")
            except urllib.error.HTTPError:
                pass
    seen, out = set(), []
    for p in sorted(pages):
        for s in pages[p] or []:
            u = s.get("user") or {}
            if u.get("login") in seen:
                continue
            seen.add(u.get("login"))
            out.append({"login": u.get("login"), "id": u.get("id"), "type": u.get("type"),
                        "starred_at": s.get("starred_at")})
    return out


def _forks(repo: str) -> list[dict]:
    try:
        lst, _ = _api(f"{API}/repos/{repo}/forks?sort=oldest&per_page={FORK_CAP}")
    except urllib.error.HTTPError:
        return []
    return [{"login": (f.get("owner") or {}).get("login"), "id": (f.get("owner") or {}).get("id"),
             "type": (f.get("owner") or {}).get("type"), "created": f.get("created_at")}
            for f in lst or []]


def build_raw(cand: dict, now: datetime | None = None) -> dict:
    """Assemble the `raw` dict for one candidate row. May raise
    discovery.RateLimited (caller stops and resumes next run)."""
    now = now or datetime.now(timezone.utc)
    repo, skill_path = cand["repo"], cand.get("skill_path", ".")
    is_collection = cand.get("distribution") == "collection"
    bundle = _repo_bundle(repo)                                   # shared across a repo's skills
    meta = bundle["meta"]
    author = (meta.get("owner") or repo.split("/")[0]).lower()
    issues = [it for it in bundle["issues"]                       # skill-level filter in collections
              if not is_collection or _mentions(it, cand.get("skill_name", ""), skill_path)]
    scope = {f: "repo" for f in ("stars", "forks", "releases", "license", "archived",
                                 "contributors", "last_commit")}
    scope["substantive_commits_90d"] = "skill" if skill_path not in ("", ".") else "repo"
    scope["independent_issue_reports"] = "skill" if is_collection else "repo"
    return {
        "candidate_id": cand["candidate_id"], "content_hash": cand.get("content_hash", ""),
        "fetched_at": now.isoformat(), "author": author, "is_collection": is_collection,
        "first_seen": cand.get("first_seen"),
        "repo_meta": meta, "author_account": bundle["author"],
        "contributors": bundle["contributors"],
        "commits": _commits(repo, skill_path, now),              # skill-level (path-filtered)
        "issues": issues,
        "stargazers": bundle["stargazers"],
        "forks": bundle["forks"],
        "scope": scope,
    }
