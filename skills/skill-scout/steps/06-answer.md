# Step 6 — Answer

1. Fill `references/output-template.md` from `ranked.json`. Use only its fields. Add no new claims.
2. On the "Works in" line, list every harness in `display_harnesses`, in order, using `harness_names`.
3. `none_found: true` → say no skill passed the checks. Name the closest `set_aside` entry and its reason, if any. Suggest building a skill instead.
4. If #1 is not `verified` and `verification_available` is true, offer the test: run `python scripts/verify.py --estimate <candidate_id> --harness <host_harness>` and state the estimate.
5. Keep it scannable. Put detail in sources, not in prose.
