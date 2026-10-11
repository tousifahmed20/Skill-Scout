#!/usr/bin/env python3
"""Assemble the evaluation evidence for one candidate (stage 06). Standard
library only. Shared by the shipped skill (cache miss) and the owner's seeding
run. Output is budgeted (evidence-budget.md) and every repo chunk is wrapped as
untrusted (injection-defense.md).

    python fetch_evidence.py <candidate_id>            # resolve via the index DB
    python fetch_evidence.py <candidate_id> --checkout DIR   # read local files (no network)

File bytes come from raw.githubusercontent.com at the pinned commit (not counted
against the REST limit); the file tree and issues are the only API calls, so a
candidate costs <= 3 and a 5-candidate query stays under the anonymous limit.
"""
from __future__ import annotations
import argparse
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import github_auth

RAW = "https://raw.githubusercontent.com"
TOKEN_CAP = 6000            # ~input tokens; cut in reverse budget order when over
CHARS_PER_TOKEN = 4
ZERO_WIDTH = "​‌‍‎‏⁠﻿"

api_calls = 0               # Done-when: <= 3 per candidate


def _default_db() -> Path:
    return Path(os.environ.get("SKILL_SCOUT_INDEX") or (Path.home() / ".skill-scout" / "index.sqlite"))


def resolve(candidate_id: str, db: Path) -> dict:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT candidate_id, repo, skill_path, commit_sha FROM candidate WHERE candidate_id=?",
                       (candidate_id,)).fetchone()
    conn.close()
    if not row:
        raise KeyError(f"{candidate_id} not in index {db}")
    return dict(row)


# ---- fetchers (raw CDN = uncounted; api_get = counted) -----------------------
def _raw(repo: str, sha: str, path: str) -> str | None:
    url = f"{RAW}/{repo}/{sha}/{urllib.parse.quote(path)}"
    req = urllib.request.Request(url, headers={"User-Agent": "skill-scout"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.URLError:
        return None


def _api(path: str, token):
    global api_calls
    api_calls += 1
    return github_auth.api_get(path, token)


def _tree(repo: str, sha: str, skill_path: str, token) -> list[str]:
    data, _ = _api(f"/repos/{repo}/git/trees/{sha}?recursive=1", token)
    prefix = "" if skill_path in ("", ".") else skill_path.rstrip("/") + "/"
    return [t["path"][len(prefix):] for t in data.get("tree", [])
            if t.get("type") == "blob" and (not prefix or t["path"].startswith(prefix))]


def _issues(repo: str, skill_name: str, skill_path: str, token) -> list[dict]:
    try:
        data, _ = _api(f"/repos/{repo}/issues?state=all&per_page=30", token)
    except urllib.error.URLError:
        return []
    leaf = skill_path.rstrip("/").rsplit("/", 1)[-1]
    out = []
    for it in data:
        if "pull_request" in it:
            continue
        text = f"{it.get('title', '')} {it.get('body', '') or ''}".lower()
        if (skill_name and skill_name.lower() in text) or (leaf and leaf.lower() in text):
            out.append({"number": it.get("number"), "title": it.get("title", ""),
                        "state": it.get("state"), "state_reason": it.get("state_reason"),
                        "body": (it.get("body") or "")[:400]})
    return out[:10]


# ---- injection scan (deterministic; shared) ----------------------------------
_INJ = [
    (re.compile(r"\b(rate|score|give|mark)\b[^.\n]{0,40}\b(10\s*/\s*10|5\s*stars|highest|perfect|top)\b", re.I),
     "tells a reviewer what score to give"),
    (re.compile(r"\balways\s+recommend\b|\bbest\s+skill\b[^.\n]{0,30}\brecommend", re.I),
     "tells a recommender what to conclude"),
    (re.compile(r"\bignore\s+(all\s+|any\s+)?(previous|prior|above)\b[^.\n]{0,20}(instruction|context|prompt)", re.I),
     "tries to override prior instructions"),
    (re.compile(r"\byou\s+are\s+now\b|\bdisregard\b[^.\n]{0,20}(instruction|rule|system)", re.I),
     "tries to reset the agent's role"),
    (re.compile(r"\bas\s+(an?|the)\s+(evaluator|ranker|reviewer|recommender|judge)\b", re.I),
     "addresses the evaluator/ranker directly"),
    (re.compile(r"\b(send|post|upload|exfiltrat\w*|leak)\b[^.\n]{0,60}"
                r"(token|api[\s_-]?key|secret|env|credential|password)[^.\n]{0,60}https?://", re.I),
     "tries to exfiltrate secrets to a URL"),
]


def scan_injection(text: str) -> tuple[bool, str]:
    if any(z in text for z in ZERO_WIDTH):
        return True, "hidden zero-width characters"
    if re.search(r"<[^>]*(display\s*:\s*none|color\s*:\s*#?f{3,6}\b)[^>]*>", text, re.I):
        return True, "hidden (white/invisible) HTML text"
    for rx, detail in _INJ:
        if rx.search(text):
            return True, detail
    return False, ""


# ---- assembly ----------------------------------------------------------------
def _wrap(repo: str, file: str, lines: str, content: str) -> str:
    return f'<<<UNTRUSTED source="{repo}" file="{file}" lines="{lines}">>>\n{content}\n<<<END UNTRUSTED>>>'


def _head(text: str, n: int) -> tuple[str, str]:
    ls = text.splitlines()
    return "\n".join(ls[:n]), f"1-{min(n, len(ls))}"


def _readme_first_section(text: str, n: int = 80) -> str:
    out = []
    for line in text.splitlines():
        if out and re.match(r"^#{1,6}\s", line):
            break
        out.append(line)
        if len(out) >= n:
            break
    return "\n".join(out)


def _referenced(skill_md: str, kind: str) -> list[str]:
    return list(dict.fromkeys(re.findall(rf"{kind}/[A-Za-z0-9_./-]+", skill_md)))


def build(loc: dict, token, checkout: Path | None) -> tuple[str, dict]:
    repo, sp, sha = loc["repo"], loc["skill_path"], loc["commit_sha"]
    prefix = "" if sp in ("", ".") else sp.rstrip("/") + "/"

    def read(rel: str) -> str | None:
        if checkout is not None:
            p = checkout / rel
            return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None
        return _raw(repo, sha, prefix + rel)

    skill_md = read("SKILL.md") or ""
    name = ""
    m = re.search(r"^name:\s*(.+)$", skill_md, re.M)
    if m:
        name = m.group(1).strip()

    if checkout is not None:
        files = [p.relative_to(checkout).as_posix() for p in checkout.rglob("*") if p.is_file()]
    else:
        try:
            files = _tree(repo, sha, sp, token)
        except urllib.error.URLError:
            files = []

    sections: list[tuple[int, str]] = []   # (budget-rank, wrapped-text); higher rank cut first
    sections.append((1, _wrap(repo, prefix + "SKILL.md", "full", skill_md)))
    sections.append((2, _wrap(repo, sp or ".", "tree", "\n".join(sorted(files)))))

    # scripts: referenced first, <=300 lines total
    script_files = [f for f in files if f.startswith("scripts/")]
    ref_first = _referenced(skill_md, "scripts")
    script_files.sort(key=lambda f: (f not in [r[len(prefix):] if r.startswith(prefix) else r for r in ref_first], f))
    budget = 300
    for f in script_files:
        if budget <= 0:
            break
        txt = read(f)
        if txt is None:
            continue
        head, rng = _head(txt, budget)
        budget -= len(head.splitlines())
        sections.append((3, _wrap(repo, prefix + f, rng, head)))

    # references referenced in SKILL.md: first 100 lines, <=3
    for rel in _referenced(skill_md, "references")[:3]:
        bare = rel[len(prefix):] if rel.startswith(prefix) else rel
        txt = read(bare)
        if txt is None:
            continue
        head, rng = _head(txt, 100)
        sections.append((4, _wrap(repo, prefix + bare, rng, head)))

    readme = (read("README.md") if checkout is not None else _raw(repo, sha, "README.md"))
    if readme:
        sections.append((5, _wrap(repo, "README.md", "first-section", _readme_first_section(readme))))

    issues = [] if checkout is not None else _issues(repo, name, sp, token)
    for it in issues:
        body = f"#{it['number']} [{it['state']}/{it.get('state_reason')}] {it['title']}\n{it['body']}"
        sections.append((6, _wrap(repo, f"issue #{it['number']}", "thread", body)))

    # enforce the hard cap: drop whole sections from the bottom (reverse table order)
    def total(secs):
        return sum(len(t) for _, t in secs) // CHARS_PER_TOKEN
    sections.sort(key=lambda s: s[0])
    while total(sections) > TOKEN_CAP and len(sections) > 1:
        sections.pop()          # drop the lowest-priority chunk; SKILL.md (rank 1) is never dropped
    text = "\n\n".join(t for _, t in sections)
    inj, detail = scan_injection(skill_md + "\n" + "\n".join(t for _, t in sections))
    meta = {"candidate_id": loc["candidate_id"], "repo": repo, "commit_sha": sha,
            "approx_tokens": total(sections), "api_calls": api_calls,
            "injection_prescreen": inj, "injection_detail": detail}
    return text, meta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="fetch_evidence.py")
    ap.add_argument("candidate_id")
    ap.add_argument("--db", default=None)
    ap.add_argument("--checkout", default=None, help="read files from this local skill folder (no network)")
    a = ap.parse_args(argv)

    checkout = Path(a.checkout) if a.checkout else None
    if checkout is not None:
        parts = a.candidate_id.split("@", 1)
        loc = {"candidate_id": a.candidate_id, "repo": parts[0],
               "skill_path": parts[1] if len(parts) > 1 else ".", "commit_sha": "local"}
    else:
        loc = resolve(a.candidate_id, Path(a.db) if a.db else _default_db())
    token, _ = github_auth.get_token()
    text, meta = build(loc, token, checkout)
    sys.stderr.write(f"# {meta}\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
