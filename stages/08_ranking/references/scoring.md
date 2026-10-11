# Scoring

Every number lives in `skills/skill-scout/references/ranking-config.json`. This file names the config keys.

## Pipeline
1. **Retrieve:** stage 05's `search(search_terms + capabilities)` with its default `k`.
2. **Exclude:** candidate `status` ≠ `active`; `injection_detected`; verification verdict in `floor.drop_verdicts`.
3. **Shortlist (no LLM):** pre-score = relevance × mean of available normalized Hard and Medium health signals. Keep the top `retrieval.evaluate_top`, plus the `retrieval.gem_reserve` most relevant new skills (see `CLAUDE.md`). New skills have no health history, so they get reserved seats instead of competing on it. `to_evaluate` = shortlisted candidates whose evaluation is `missing` or `stale`, at most `retrieval.max_evaluations_per_query`.
4. **Harness and constraints:**
   - Effective level = stage 03 level, raised to `incompatible` when the evaluation's `core_depends_on` names a feature the host lacks.
   - `incompatible` with the host → set aside. Keep the best one for a one-line note.
   - User constraints (OS, "free only", offline) that a skill's requirements break → set aside, with the reason.
   - `unknown` level stays, shown with "?".
   - Host harness `unknown` → no harness filter; show levels only.
5. **Fit (model, in step 4):** only candidates with an evaluation can be judged; the rest are counted in `not_evaluated`. `full` = covers every requested capability; `partial` = covers some (list `missing`); `none` → drop. Judge from `capabilities` and `actually_does`, never from the description.
6. **Floor:** credibility ≥ `floor.min_credibility` and unsupported core claims ≤ `floor.max_unsupported_core`. Fail → drop. Never pad.
7. **Score:** `final = Σ points[signal] × s[signal]`, with each `s` in 0–1, normalized as a percentile within the skill's primary cluster.
   - No verification → move `behavioral_delta` points proportionally to the other Hard signals. Cap evidence level at `inspected`.
   - A missing Soft signal → move its points to the other Soft signals.
8. **Order:** `full` fits by score, then `partial` fits by score. Ties: host level `compatible` > `partial` > `unknown`, then evidence level.
9. **Gem slot:** see `engines.md`.
10. **Flags:** `star_burst` → `suspicious_popularity`. Popularity percentile − credibility percentile ≥ `flags.unproven_gap_percentile` → `popular_but_unproven`.
11. **Differentiator:** the signal with the largest weighted gap between #1 and #2.
12. No pick survives → `none_found: true`.

## Credibility
`credibility = Σ w·[supported] / Σ w·[supported or unsupported] − credibility.penalty_per_unsupported_core × (unsupported core claims)`, clamped to 0–1. `w` = `credibility.core_weight` or `credibility.minor_weight`. No verifiable claims → `credibility.neutral_if_no_verifiable_claims`.

## Signals → s
| Signal | Tier | s |
|---|---|---|
| `behavioral_delta` | Hard | percentile of verification `delta` (confirmed or single) |
| `claims_evidence` | Hard | credibility |
| `independent_reports` | Hard | 0.5 × percentile(usage) + 0.5 × resolution. Usage = `independent_issue_reports` + firsthand external reports + outcome reports. Resolution = fixed ÷ (fixed + `closed_unresolved`), using evaluation `confirmed_fixed` + health `linked_fix_closures`; no data → 0.5 |
| `substantive_commits` | Hard | percentile of `substantive_commits_90d`; × 0.5 when `commit_padding` |
| `contributor_independence` | Medium | percentile of `independent_contributors` |
| `example_realism` | Medium | evaluation value |
| `instruction_specificity` | Medium | evaluation value |
| `star_velocity_quality` | Soft | percentile of `star_velocity_7d × stargazer_quality`; 0 when `star_burst`; × `repo_scope_factor` when scope is repo |
| `installs` | Soft | percentile; × `repo_scope_factor` when scope is repo |
| `forks_releases_license` | Soft | mean of percentile(forks), releases > 0, license present |

Repo-level signals never rank sibling skills in one collection against each other.

## Signal slots
Later stages fill these tables. Ranking reads them when rows exist.

`external_reports` (filled by stage 11)
| Field | Type |
|---|---|
| `candidate_id` | text |
| `url`, `source` | text |
| `posted_at` | timestamp |
| `firsthand` | bool — the author says they used it |
| `sentiment` | `positive` · `negative` · `mixed` · `neutral` |
| `summary` | text, ≤ 200 chars |
| `launch_window` | bool — inside a coordinated-launch cluster |

Only `firsthand = true` and `launch_window = false` rows count as usage. Negative firsthand rows also go to limitations, with the URL as evidence.

`outcome_reports` (filled through the store, stages 09 and 10)
| Field | Type |
|---|---|
| `candidate_id` | text |
| `worked` | `yes` · `partial` · `no` |
| `harness` | harness id |
| `note` | text, ≤ 200 chars |
| `contributor_id` | text |
