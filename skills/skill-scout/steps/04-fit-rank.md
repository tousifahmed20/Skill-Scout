# Step 4 — Fit, then rank

1. For each candidate in `shortlist.json` that has an evaluation (cached or new `eval-<n>.json`), compare the user's `capabilities` with the candidate's `capabilities` and `actually_does`. Use only these evidence fields, never the description or README.
   - `full`: covers every requested capability.
   - `partial`: covers some. List the missing ones.
   - `none`: covers none of the core need.
2. Write `fits.json`: `[{"candidate_id": "", "fit": "full | partial | none", "missing": []}]`.
3. Run `python scripts/rank.py rank --task task.json --fits fits.json > ranked.json`.
4. Use `ranked.json` as it is. Do not reorder, add, or drop picks by hand.
