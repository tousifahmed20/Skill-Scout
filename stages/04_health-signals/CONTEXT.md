# 04 · health-signals (Layer 2)

**Job:** compute free signals for each skill from the GitHub API, and flag gaming. No LLM. This stage stores raw values; stage 08 normalizes and weights them.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/04_health-signals/references/signals.md` | all | what to measure and how |
| `stages/04_health-signals/references/anti-gaming.md` | all | detectors |

## Process
1. For each candidate, fetch repo and skill-folder data: commits, issues, contributors, stargazers, releases, license, archived state.
2. Measure at skill level where possible (commits that touch the skill folder; issues that mention the skill name or path). Fall back to repo level and record the scope.
3. Run the detectors. Set flags.
4. Refresh weekly. Refresh new skills (see `CLAUDE.md`) daily.

## Outputs
| Path | What |
|---|---|
| `src/health/` | fetchers, measures, detectors; `schema.sql` for the health table |
| `data/fixtures/gaming/` | seeded examples for each detector |
| `tests/health/` | tests |

## Output record
```json
{
  "candidate_id": "", "computed_at": "",
  "independent_issue_reports": 0, "linked_fix_closures": 0, "closed_without_fix": 0,
  "substantive_commits_90d": 0, "median_diff_lines": 0,
  "contributors": 0, "independent_contributors": 0,
  "maintainer_first_response_h": null,
  "stars": 0, "star_velocity_7d": 0, "stargazer_quality": 0.0,
  "installs": null, "forks": 0, "releases": 0, "license": null,
  "archived": false, "last_commit": "",
  "author_track_record": 0.0, "early_organic_traction": 0.0,
  "scope": {"<field>": "skill | repo"},
  "flags": ["star_burst | commit_padding | sock_puppets | self_filed_issues"]
}
```

## Done when
- Each detector flags its seeded fixture and does not flag a clean control.
- Signals are computed for 1,000 candidates within the GitHub rate limits.
