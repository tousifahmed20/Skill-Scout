# Step 2 — Retrieve

1. Run `python scripts/rank.py retrieve --task task.json > shortlist.json`.
2. Read only these fields of `shortlist.json`: `to_evaluate`, and for each candidate `candidate_id`, `skill_name`, `evaluation_freshness`, and `evaluation.capabilities` / `evaluation.actually_does` when present.
3. If `to_evaluate` is not empty → step 3. Otherwise → step 4.
