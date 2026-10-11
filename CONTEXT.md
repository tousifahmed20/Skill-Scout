# Routing (Layer 1)

Pick the row for the task. Open that stage's `CONTEXT.md`. Its Inputs table is the complete read set.

- `single` — the stage folder only (plus the files it owns).
- `multi: NN, …` — the stage folder plus named sections from those earlier stages. The exact paths and sections live in the stage's Inputs table, not here.

| # | Stage | Task | Owns (main path) | Read set |
|---|---|---|---|---|
| 01 | golden-set | label calibration skills and tasks; seeding cost estimate | `data/golden-set/` | single |
| 02 | collector | find skills; membership, safety, dedupe | `src/collector/` | single |
| 03 | compatibility | harness compatibility and requirements | `src/compatibility/` | single |
| 04 | health-signals | free repo signals; anti-gaming detectors | `src/health/` | single |
| 05 | clustering | clusters, labels, text search for the skill | `src/clustering/` | single |
| 06 | evaluation | claims vs evidence (LLM, sampled) | `src/evaluation/` | single |
| 07 | verification | with/without skill test (opt-in, user machine) | `skills/skill-scout/scripts/verify.py` | multi: 03, 06 |
| 08 | ranking | fit gate, floor, harness filter, score, engines | `src/ranking/` | multi: 02, 03, 04, 05, 06, 07 |
| 09 | skill-client | assemble and test the shipped skill | `skills/skill-scout/SKILL.md` | multi: 03, 06, 07, 08 |
| 10 | hive | **v2** — shared cache API, consensus, privacy, spend cap | `src/hive/` | multi: 05, 06, 07, 08 |
| 11 | external-signals | **v2** — firsthand reports from Hacker News and Reddit | `src/external/` | multi: 08 |

## Other tasks
- Bug or change in a file → the stage that owns it (see each stage's Outputs table).
- Task spans two stages → finish the lower-numbered stage first, update `PROGRESS.md`, then move on.
- "Why was this decided?" → `docs/decisions.md`, only when the user asks.
- Build order = stage order. Do not start a stage until the previous stage's Done-when passes.
- v1 (free launch) ends at stage 09. Do not start stages 10–11 until `PROGRESS.md` says v2 has started.
