# Step 5 — Verify (only when the user agrees)

1. Run `python scripts/verify.py --estimate <candidate_id> --harness <id>`. Tell the user the estimated tokens. Continue only on a clear yes.
2. If the skill has scripts, ask a second time and name the scripts.
3. Run `python scripts/verify.py --setup <candidate_id>`. It prints the temporary folder path.
4. Follow `references/verification-protocol.md` in that folder. Use the harness's verification runner for each fresh context.
5. Write the record to `verify-<candidate>.json` and run `python scripts/verify.py --finish verify-<candidate>.json` (validates, deletes the folder).
6. Return to step 4 to re-rank with the new result.
