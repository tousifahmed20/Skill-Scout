"""Discover agent-skill folders from the sources in
`stages/02_collector/references/sources.md`.

Auth: the scheduled build passes the owner token in env `AF_GITHUB_TOKEN`
(fallback `GITHUB_TOKEN`). Every GitHub API call is authenticated when a token
is present. On a rate-limit response we back off; if the wait is long we raise
`RateLimited` so the pipeline can persist its cursor and resume next run
(sources.md: never drop work silently). Raw file bytes come from the
raw.githubusercontent.com CDN, which is unmetered.
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
KNOWN_COLLECTIONS = [
    "anthropics/skills", "openai/skills", "vercel-labs/agent-skills",
    "github/awesome-copilot", "huggingface/skills",
]
TOPICS = ["agent-skills", "claude-skills", "claude-code-skills",
          "codex-skills", "gemini-skills", "antigravity-skills"]
_FILE_BUCKETS = {"scripts": "scripts", "references": "references", "assets": "assets"}
MAX_BACKOFF_SECONDS = 900  # beyond this, stop and resume next run instead of sleeping


class RateLimited(Exception):
    def __init__(self, reset_epoch: float):
        super().__init__(f"rate limited until {reset_epoch}")
        self.reset_epoch = reset_epoch


@dataclass
class RawSkill:
    repo: str
    skill_path: str            # folder holding SKILL.md ("." = repo root)
    commit_sha: str
    distribution: str          # repo | collection | plugin
    plugin_manifest: str | None
    folder_files: list[str]    # paths relative to skill_path
    files: dict[str, bytes]    # relative path -> bytes (for hashing + checkout)
    skill_md_text: str | None
    files_categorized: dict = field(default_factory=dict)
    first_seen: str | None = None
    last_changed: str | None = None

    @property
    def candidate_id(self) -> str:
        return f"{self.repo}@{self.skill_path}"


def _token() -> str | None:
    return os.environ.get("AF_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")


def _request(url: str, accept: str = "application/vnd.github+json"):
    headers = {"User-Agent": "skill-scout", "Accept": accept}
    tok = _token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return urllib.request.Request(url, headers=headers)


def _api(url: str, _retries: int = 3):
    """GET a GitHub API URL, returning (json, resp_headers). Backs off on a
    rate-limit; raises RateLimited if the reset is far away."""
    try:
        with urllib.request.urlopen(_request(url), timeout=30) as r:
            return json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        remaining = e.headers.get("X-RateLimit-Remaining")
        if e.code in (403, 429) and remaining == "0":
            reset = float(e.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = reset - time.time()
            if wait > MAX_BACKOFF_SECONDS:
                raise RateLimited(reset) from None
            time.sleep(max(1.0, wait) + 1)
            if _retries > 0:
                return _api(url, _retries - 1)
        raise


def _raw(repo: str, sha: str, path: str) -> bytes:
    url = f"{RAW}/{repo}/{sha}/{urllib.parse.quote(path)}"
    with urllib.request.urlopen(_request(url, accept="*/*"), timeout=30) as r:
        return r.read()


def _repo_head(repo: str) -> tuple[str, str] | None:
    meta, _ = _api(f"{API}/repos/{repo}")
    if meta.get("message"):
        return None
    branch = meta["default_branch"]
    ref, _ = _api(f"{API}/repos/{repo}/git/refs/heads/{urllib.parse.quote(branch)}")
    return ref["object"]["sha"], branch


def _commit_dates(repo: str, path: str) -> tuple[str | None, str | None]:
    """(first_seen, last_changed) ISO dates for commits touching `path`."""
    q = f"{API}/repos/{repo}/commits?per_page=1&path={urllib.parse.quote(path)}"
    page1, headers = _api(q)
    if not page1:
        return None, None
    last_changed = page1[0]["commit"]["committer"]["date"][:10]
    link = headers.get("Link", "")
    first_seen = last_changed
    if 'rel="last"' in link:
        import re
        m = re.search(r'<([^>]+)>;\s*rel="last"', link)
        if m:
            last_page, _ = _api(m.group(1))
            if last_page:
                first_seen = last_page[-1]["commit"]["committer"]["date"][:10]
    return first_seen, last_changed


def _categorize(folder_files: list[str]) -> dict:
    out = {"scripts": [], "references": [], "assets": [], "other": []}
    for f in folder_files:
        if f == "SKILL.md":
            continue
        top = f.split("/", 1)[0]
        out[_FILE_BUCKETS.get(top, "other")].append(f)
    return out


def enumerate_repo(repo: str) -> list[dict]:
    """Return one dict per SKILL.md folder in the repo: skill_path, folder_files,
    distribution, plugin_manifest, commit_sha."""
    head = _repo_head(repo)
    if not head:
        return []
    sha, _ = head
    tree, _ = _api(f"{API}/repos/{repo}/git/trees/{sha}?recursive=1")
    blobs = [t["path"] for t in tree.get("tree", []) if t["type"] == "blob"]
    plugin_manifests = [p for p in blobs
                        if p.endswith(".claude-plugin/plugin.json") or p == "plugin.json"]
    skills = []
    for p in blobs:
        if p == "SKILL.md":
            skill_path = "."
        elif p.endswith("/SKILL.md"):
            skill_path = p[: -len("/SKILL.md")]
        else:
            continue
        prefix = "" if skill_path == "." else skill_path + "/"
        folder_files = [b[len(prefix):] for b in blobs
                        if (b == prefix + "SKILL.md") or (prefix and b.startswith(prefix))
                        or (skill_path == "." and "/" not in b)]
        if skill_path == ".":
            folder_files = [b for b in blobs if "/" not in b]
        manifest = next((m for m in plugin_manifests
                         if m.rsplit("/", 1)[0].rsplit(".claude-plugin", 1)[0].rstrip("/")
                         and skill_path.startswith(m.split(".claude-plugin")[0].rstrip("/"))), None)
        distribution = "plugin" if manifest else ("collection" if repo in KNOWN_COLLECTIONS else "repo")
        skills.append({"skill_path": skill_path, "folder_files": folder_files,
                       "distribution": distribution, "plugin_manifest": manifest,
                       "commit_sha": sha})
    return skills


def fetch_skill(repo: str, meta: dict, *, with_dates: bool = True) -> RawSkill:
    sha, skill_path = meta["commit_sha"], meta["skill_path"]
    prefix = "" if skill_path == "." else skill_path + "/"
    files: dict[str, bytes] = {}
    skill_md_text = None
    for rel in meta["folder_files"]:
        data = _raw(repo, sha, prefix + rel)
        files[rel] = data
        if rel == "SKILL.md":
            skill_md_text = data.decode("utf-8", "replace")
    rs = RawSkill(repo=repo, skill_path=skill_path, commit_sha=sha,
                  distribution=meta["distribution"], plugin_manifest=meta["plugin_manifest"],
                  folder_files=meta["folder_files"], files=files, skill_md_text=skill_md_text,
                  files_categorized=_categorize(meta["folder_files"]))
    if with_dates:
        md_path = (prefix + "SKILL.md")
        rs.first_seen, rs.last_changed = _commit_dates(repo, md_path)
    return rs


def search_repos_by_topic(topic: str, pages: int = 1) -> list[str]:
    repos = []
    for page in range(1, pages + 1):
        url = f"{API}/search/repositories?per_page=50&page={page}&q={urllib.parse.quote('topic:'+topic)}"
        try:
            data, _ = _api(url)
        except urllib.error.HTTPError:
            break
        items = data.get("items", [])
        repos += [i["full_name"] for i in items]
        if len(items) < 50:
            break
    return repos


def discover_repos(include_topics: bool = True) -> list[str]:
    """Ordered, de-duplicated repo list from the sources. Code search
    (`filename:SKILL.md`) needs auth and is added by the scheduled build; topic
    + collection discovery works with or without a token."""
    seen, out = set(), []
    for repo in KNOWN_COLLECTIONS:
        if repo not in seen:
            seen.add(repo); out.append(repo)
    if include_topics and _token():  # repo search is rate-limited; skip unauth
        for topic in TOPICS:
            for repo in search_repos_by_topic(topic):
                if repo not in seen:
                    seen.add(repo); out.append(repo)
    return out
