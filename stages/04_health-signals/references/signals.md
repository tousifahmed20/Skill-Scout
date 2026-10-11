# Signals

**Established account** = account age > 30 days and some public activity.

| Field | How to measure | Notes |
|---|---|---|
| `independent_issue_reports` | Issues and discussions opened by accounts that are not the author or a contributor | Skill level in collections: issues that mention the skill name or path |
| `linked_fix_closures` | Issues closed by a linked commit or PR | Deterministic proxy. Stage 06 reads thread endings for the stronger "reporter confirmed" signal. |
| `closed_without_fix` | Issues closed with no linked fix and no maintainer reply | |
| `substantive_commits_90d` | Commits in 90 days that change the SKILL.md body, scripts, or references with a non-trivial diff | Exclude README-only, badge, whitespace, and typo commits |
| `median_diff_lines` | Median changed lines of those commits | Used by the commit-padding detector |
| `independent_contributors` | Contributors with account age > 90 days and activity in at least one other repo | |
| `maintainer_first_response_h` | Median hours to the first maintainer reply on issues | |
| `star_velocity_7d` | Stars gained in the last 7 days | Repo level |
| `stargazer_quality` | Share of recent stargazers that are established accounts | Sample up to 200 |
| `installs` | Registry install count, if available | Tiebreaker only |
| `forks`, `releases`, `license`, `archived`, `last_commit` | Repo metadata | |
| `author_track_record` | 0–1: substantive commits by the author in other public repos over the last year | Measures real work, not fame or followers |
| `early_organic_traction` | 0–1: for new skills, share of first stars, issues, and forks that come from established accounts | Used by the Hidden Gem engine |
