# Step 7 — Share results

For each new result file, run:
- `python scripts/store.py put --kind evaluation --file eval-<n>.json`
- `python scripts/store.py put --kind verification --file verify-<candidate>.json`
- `python scripts/store.py put --kind outcome_report --file outcome.json` (only when the user reports whether a pick worked)

In the free version (local store), results are saved only on this computer and reused on later queries. Nothing is uploaded.

Send structured results only. Never send the user's code, files, keys, or the raw task sentence. The store prints any notice the user must see; show it to them unchanged.

If a `put` is not accepted, tell the user the reason in one line. The answer they already got stays valid.
