# Step 3 — Evaluate cache misses

Evaluate only the candidates listed under `to_evaluate` in `shortlist.json`, in the order given.

First run `python scripts/github_auth.py status`. If it prints `anonymous`, continue anyway; most queries fit the free limit.

For each candidate:
1. Run `python scripts/fetch_evidence.py <candidate_id> > evidence.txt`.
2. Evaluate `evidence.txt` with `references/evaluation-rubric.md`. Write the JSON to `eval-<n>.json`.
3. Run `python scripts/validate_evaluation.py eval-<n>.json`.
4. If validation fails, fix only the reported fields and validate once more. If it fails again, drop the candidate and say why in the answer.

If `fetch_evidence.py` reports that the GitHub limit was reached, stop evaluating, go to step 4 with what you have, and show the user `references/github-setup.md` after the answer.

Do not evaluate candidates that are not listed. If `shortlist.json` reports more misses than listed, say in the answer that some candidates were not evaluated.
