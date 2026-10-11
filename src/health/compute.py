"""Pure health measures + anti-gaming detectors (stage 04). No network, no LLM.

Everything here takes one `raw` dict (facts fetched from the GitHub API by
fetch.py, or a seeded fixture) and returns the stage-04 output record
(stages/04_health-signals/CONTEXT.md). Keeping it pure is what lets the
detector fixtures in data/fixtures/gaming/ run without a network.

`raw` shape (every field optional; missing facts just yield conservative zeros):
    {
      "candidate_id", "content_hash", "fetched_at" (ISO),
      "author": "<owner-login>",
      "is_collection": bool,                 # many skills in one repo
      "first_seen": "YYYY-MM-DD" | None,     # earliest SKILL.md commit (candidate)
      "repo_meta": {"stars","forks","archived","license","pushed_at",
                    "releases","last_commit"},
      "author_account": {"created_at","public_repos","id","type"} | None,
      "contributors": [{"login","created_at","public_repos","id","type"}],
      "commits": [{"sha","date","login","additions","deletions","files":[...]}],
      "issues":  [{"login","author_association","created_at","closed_at",
                   "state_reason","maintainer_reply_h"}],
      "stargazers": [{"login","id","type","starred_at","created_at","public_repos"}],
      "forks": [{"login","id","created_at","public_repos","type","created"}],
      "scope": {field: "skill"|"repo"},
    }

Account facts may be partial: when an account carries `created_at` we apply the
real "established" rule (signals.md); for a stargazer sample that only carries a
numeric id we fall back to a monotonic-id proxy (see `_established`).
"""
from __future__ import annotations
import statistics
from datetime import datetime, timezone

# --- tunable thresholds (anti-gaming.md: tune in fixtures, not in prod) --------
ESTABLISHED_MIN_AGE_DAYS = 30          # signals.md: account age > 30 days
INDEPENDENT_MIN_AGE_DAYS = 90          # signals.md: independent contributor age
NEW_SKILL_DAYS = 14                    # CLAUDE.md: first_seen <= 14d ago
SUBSTANTIVE_MIN_LINES = 5              # a commit changing fewer lines is a typo/badge
SUBSTANTIVE_FILES = ("SKILL.md",)      # or anything under these dirs:
SUBSTANTIVE_DIRS = ("scripts/", "references/")
# "Established" is decided only from created_at + public_repos (signals.md). The
# list endpoints for stargazers/forks/issue-authors don't carry those, so for
# those accounts establishment is *unknown* and the signals that need it degrade
# (stargazer_quality -> None; star_burst's unestablished-share and the star/fork
# part of early_organic_traction stay inert) rather than guess. ponytail: a user
# id is NOT a reliable age proxy (the threshold drifts and can't be verified);
# enabling these live = a bounded per-account /users enrichment of the sample.

COMMIT_PADDING_MIN_COMMITS = 10        # many commits...
COMMIT_PADDING_MAX_MEDIAN = 2          # ...but each a near-empty diff
STAR_BURST_WINDOW_H = 48
STAR_BURST_MIN_STARS = 20              # a burst smaller than this is just interest
STAR_BURST_UNESTABLISHED_SHARE = 0.7   # most of the burst is fresh/throwaway accounts
SOCK_PUPPET_CLUSTER_DAYS = 7           # contributor accounts born within a week...
SOCK_PUPPET_MIN_CLUSTER = 3            # ...at least this many...
SOCK_PUPPET_MAX_PUBLIC_REPOS = 1       # ...with no outside activity


def _now(raw: dict) -> datetime:
    f = raw.get("fetched_at")
    return _parse(f) or datetime.now(timezone.utc)


def _parse(s) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(s if "T" in s or "+" in s else s + "T00:00:00+00:00")
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _age_days(created, now: datetime) -> float | None:
    d = _parse(created)
    return (now - d).days if d else None


def _age_hours(ts, now: datetime) -> float | None:
    d = _parse(ts)
    return (now - d).total_seconds() / 3600 if d else None


def _established(acc: dict, now: datetime) -> bool | None:
    """signals.md: age > 30d AND some public activity. Returns None when the
    account carries no created_at (establishment unknown — see the note above)."""
    if not isinstance(acc, dict) or _age_days(acc.get("created_at"), now) is None:
        return None
    return _age_days(acc.get("created_at"), now) > ESTABLISHED_MIN_AGE_DAYS \
        and int(acc.get("public_repos", 0) or 0) >= 1


def _is_new(raw: dict, now: datetime) -> bool:
    age = _age_days(raw.get("first_seen"), now)
    return age is not None and age <= NEW_SKILL_DAYS


def _author_logins(raw: dict) -> set[str]:
    out = {str(raw.get("author", "")).lower()}
    out |= {str(c.get("login", "")).lower() for c in raw.get("contributors", [])}
    return {x for x in out if x}


def _substantive(commit: dict) -> bool:
    files = commit.get("files") or []
    touches = any(f == sf for f in files for sf in SUBSTANTIVE_FILES) or \
        any(f.startswith(d) for f in files for d in SUBSTANTIVE_DIRS) or not files
    lines = int(commit.get("additions", 0) or 0) + int(commit.get("deletions", 0) or 0)
    return touches and lines >= SUBSTANTIVE_MIN_LINES


# --- measures -----------------------------------------------------------------
def _measure(raw: dict, now: datetime) -> dict:
    meta = raw.get("repo_meta") or {}
    authors = _author_logins(raw)

    issues = raw.get("issues") or []
    indep_reports = linked = closed_nofix = 0
    first_resp = []
    for it in issues:
        login = str(it.get("login", "")).lower()
        assoc = str(it.get("author_association", "")).upper()
        self_filed = login in authors or assoc in ("OWNER", "MEMBER", "COLLABORATOR")
        if not self_filed:
            indep_reports += 1
        if it.get("closed_at"):
            # ponytail: state_reason=completed is the deterministic linked-fix proxy
            # signals.md sanctions; the timeline API gives the exact linked PR/commit.
            if it.get("state_reason") == "completed":
                linked += 1
            elif it.get("state_reason") in ("not_planned", None):
                closed_nofix += 1
        r = it.get("maintainer_reply_h")
        if isinstance(r, (int, float)):
            first_resp.append(float(r))

    commits = raw.get("commits") or []
    sub = [c for c in commits if _substantive(c)]
    diffs = [int(c.get("additions", 0) or 0) + int(c.get("deletions", 0) or 0) for c in sub]
    median_diff = int(statistics.median(diffs)) if diffs else 0

    contribs = raw.get("contributors") or []
    indep_contrib = sum(
        1 for c in contribs
        if str(c.get("login", "")).lower() != str(raw.get("author", "")).lower()
        and (_age_days(c.get("created_at"), now) or 0) > INDEPENDENT_MIN_AGE_DAYS
        and int(c.get("public_repos", 0) or 0) >= 2      # active in another repo (proxy)
    )

    stg = raw.get("stargazers") or []
    recent = [s for s in stg if (h := _age_hours(s.get("starred_at"), now)) is not None and h <= 7 * 24]
    known = [e for s in stg if (e := _established(s, now)) is not None]
    quality = round(sum(known) / len(known), 3) if known else None   # None = not measured

    return {
        "independent_issue_reports": indep_reports,
        "linked_fix_closures": linked,
        "closed_without_fix": closed_nofix,
        "substantive_commits_90d": len(sub),
        "median_diff_lines": median_diff,
        "contributors": len(contribs),
        "independent_contributors": indep_contrib,
        "maintainer_first_response_h": round(statistics.median(first_resp), 1) if first_resp else None,
        "stars": int(meta.get("stars", 0) or 0),
        "star_velocity_7d": len(recent),
        "stargazer_quality": quality,
        "installs": raw.get("installs"),
        "forks": int(meta.get("forks", 0) or 0),
        "releases": int(meta.get("releases", 0) or 0),
        "license": meta.get("license"),
        "archived": bool(meta.get("archived", False)),
        "last_commit": meta.get("last_commit"),
        "author_track_record": _author_track_record(raw, now),
        "early_organic_traction": _early_organic_traction(raw, now),
    }


def _author_track_record(raw: dict, now: datetime) -> float:
    """0-1 proxy for real outside work. ponytail: from the author account object
    we already fetch (public_repos + age); the faithful 'substantive commits in
    other repos last year' needs /search/commits — the upgrade path."""
    acc = raw.get("author_account")
    if not isinstance(acc, dict):
        return 0.0
    age = _age_days(acc.get("created_at"), now) or 0
    repos = int(acc.get("public_repos", 0) or 0)
    score = min(repos / 10.0, 0.6) + (0.4 if age > 365 else age / 365 * 0.4)
    return round(min(score, 1.0), 3)


def _early_organic_traction(raw: dict, now: datetime) -> float:
    """New skills only: share of the first stars/issues/forks from established
    accounts (signals.md; Hidden Gem engine, stage 08). 0 for non-new skills."""
    if not _is_new(raw, now):
        return 0.0
    first = _parse(raw.get("first_seen"))
    if not first:
        return 0.0

    def early(ts) -> bool:                       # event within the new-skill window
        age = _age_days(ts, first)
        return age is not None and age <= NEW_SKILL_DAYS

    actors = []                                  # only accounts with KNOWN establishment
    for s in raw.get("stargazers") or []:
        if early(s.get("starred_at")) and (e := _established(s, now)) is not None:
            actors.append(e)
    for it in raw.get("issues") or []:
        if early(it.get("created_at")) and (e := _established(it.get("account", it), now)) is not None:
            actors.append(e)
    for fk in raw.get("forks") or []:
        if early(fk.get("created")) and (e := _established(fk, now)) is not None:
            actors.append(e)
    return round(sum(actors) / len(actors), 3) if actors else 0.0


# --- detectors (anti-gaming.md) -----------------------------------------------
def _detect(raw: dict, m: dict, now: datetime) -> list[str]:
    flags = []

    # star_burst: STAR_BURST_MIN_STARS+ stars inside 48h, mostly unestablished.
    stg = raw.get("stargazers") or []
    burst = [s for s in stg if (h := _age_hours(s.get("starred_at"), now)) is not None and h <= STAR_BURST_WINDOW_H]
    if len(burst) >= STAR_BURST_MIN_STARS:
        # Ratio over accounts whose establishment is known; unknown ones don't
        # count either way, so a burst of unreadable accounts won't false-fire.
        known = [e for s in burst if (e := _established(s, now)) is not None]
        unestablished = sum(1 for e in known if not e)
        if known and unestablished / len(known) >= STAR_BURST_UNESTABLISHED_SHARE:
            flags.append("star_burst")

    # commit_padding: many commits, tiny median diff.
    commits = raw.get("commits") or []
    if len(commits) >= COMMIT_PADDING_MIN_COMMITS:
        diffs = [int(c.get("additions", 0) or 0) + int(c.get("deletions", 0) or 0) for c in commits]
        if diffs and statistics.median(diffs) <= COMMIT_PADDING_MAX_MEDIAN:
            flags.append("commit_padding")

    # sock_puppets: >=3 contributor accounts born within a week, no outside activity.
    born = sorted(d for c in raw.get("contributors") or []
                  if (d := _parse(c.get("created_at"))) is not None
                  and int(c.get("public_repos", 0) or 0) <= SOCK_PUPPET_MAX_PUBLIC_REPOS)
    for i, b in enumerate(born):
        cluster = [x for x in born[i:] if (x - b).days <= SOCK_PUPPET_CLUSTER_DAYS]
        if len(cluster) >= SOCK_PUPPET_MIN_CLUSTER:
            flags.append("sock_puppets")
            break

    # self_filed_issues: any issue opened by the author's / a contributor's account.
    authors = _author_logins(raw)
    if any(str(it.get("login", "")).lower() in authors
           or str(it.get("author_association", "")).upper() in ("OWNER", "MEMBER", "COLLABORATOR")
           for it in raw.get("issues") or []):
        flags.append("self_filed_issues")

    return flags


def compute(raw: dict) -> dict:
    """raw -> stage-04 output record (CONTEXT.md). Pure."""
    now = _now(raw)
    m = _measure(raw, now)
    rec = {
        "candidate_id": raw.get("candidate_id", ""),
        "content_hash": raw.get("content_hash", ""),
        "computed_at": (raw.get("fetched_at") or datetime.now(timezone.utc).isoformat()),
        **m,
        "scope": raw.get("scope", {}),
        "flags": _detect(raw, m, now),
    }
    return rec
