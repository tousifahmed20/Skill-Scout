# Engines

Numbers are under `gem` and `famous` in `ranking-config.json`.

## Hidden Gem (daily job)
- **Population:** new skills (see `CLAUDE.md`), any star count.
- **Ignores the Soft tier.** Gem score = `Σ gem.points[signal] × s`:
  - `instruction_specificity` (evaluation)
  - `claims_to_substance` = 1 − `hype_score`
  - `structural_seriousness` = scripts, references, or examples present × `example_realism`
  - `author_track_record` (health)
  - `early_organic_traction` (health)
- **Slot 3 rule:** the best gem takes slot 3 when it scores ≥ `gem.min_gem_score`, passes the floor, has `fit: full`, has no flags, and is not already in the top 3. Badge: `hidden-gem`, shown as "Hidden Gem — less battle-tested".
- **v1:** no owner LLM spend on new skills. Their reserved shortlist seats send them to `to_evaluate`, so the user's own session evaluates them; the result stays on that machine.
- **Graduation:** at `gem.graduate_age_days`, or after `gem.graduate_outcome_reports` outcome reports, it competes only in the normal score.

## Famous (weekly job plus triggers)
- **Population:** first seen > `famous.min_age_days`.
- **Refresh:** every `famous.refresh_days`, and on a trigger: new release, issue spike, change to `content_hash`, or a challenger in the same cluster rising fast.
- **Job:** recompute flags. Large popularity-to-credibility gaps get `popular_but_unproven`.
