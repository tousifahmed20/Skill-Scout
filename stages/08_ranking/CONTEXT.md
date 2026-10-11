# 08 · ranking (Layer 2)

**Job:** for one normalized task and the user's harness, return at most 3 picks that fit the task, pass a quality floor, and run in that harness — ordered by evidence, not popularity.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/08_ranking/references/scoring.md` | all | pipeline, signal definitions, slots (owned here) |
| `stages/08_ranking/references/engines.md` | all | Hidden Gem and Famous engines |
| `skills/skill-scout/references/ranking-config.json` | all | every number: points, thresholds (owned here) |
| `stages/02_collector/references/candidate-schema.md` | `#candidate-record` | `first_seen`, `distribution`, `status` |
| `stages/03_compatibility/CONTEXT.md` | `#output-record` | harness levels, requirements |
| `stages/04_health-signals/CONTEXT.md` | `#output-record` | raw signals and flags |
| `stages/05_clustering/CONTEXT.md` | `#process` | `search()`, clusters, labels |
| `skills/skill-scout/references/evaluation-rubric.md` | `#output-schema` | evaluation fields |
| `stages/07_verification/CONTEXT.md` | `#output-record` | delta, verdict, status |

## Process
1. Implement the Store interface below with the `local` backend.
2. Implement `rank.py`: `task-template`, `retrieve` (pipeline steps 1–4 in `scoring.md`), and `rank` (steps 5–12). The server wrapper in `src/ranking/` calls the same code.
3. Implement the engines in `engines.md` as jobs in `src/ranking/` (run by GitHub Actions; no LLM).
4. Create the `external_reports` and `outcome_reports` slot tables (empty until stages 10 and 11 fill them).
5. Write the runtime fit-and-rank step.

## Task input
`rank.py task-template` prints this; step 1 of the skill fills it.
```json
{
  "task_text": "the user's sentence",
  "task_label": "≤ 8 words",
  "capabilities": ["2–6 verb phrases"],
  "search_terms": ["8–15 keywords and synonyms for the task"],
  "constraints": {"os": null, "free_only": false, "offline": false, "language": null},
  "host_harness": "<harness id or unknown>"
}
```

## Store interface
```
Store.search(terms, k)        -> [(candidate_id, relevance)]
Store.bundle(candidate_id)    -> {candidate, compatibility, health,
                                  evaluation | null, evaluation_freshness: fresh | stale | missing,
                                  verification | null, outcome_summary}
Store.put(kind, record)       -> {accepted: bool, reason}
                                 kind: evaluation | verification | outcome_report
```
Backends, selected with env `SKILL_SCOUT_STORE`:
- `local` (this stage; the v1 default): reads the index at the skill cache path (see `CLAUDE.md`) and downloads the latest release asset when it is missing or older than 24 h. `put` writes only to the user's `local.sqlite`, which overlays the index on later queries. Nothing leaves the machine.
- `remote` (stage 10, v2).

## Outputs
| Path | What |
|---|---|
| `skills/skill-scout/scripts/rank.py` | `task-template`, `retrieve`, `rank` — one implementation for client and server |
| `skills/skill-scout/scripts/store.py` | Store interface and `local` backend |
| `skills/skill-scout/references/ranking-config.json` | all ranking numbers — single home |
| `skills/skill-scout/steps/04-fit-rank.md` | runtime step: fit labels, then `rank.py rank` |
| `src/ranking/` | server wrapper, engine jobs; `schema.sql` for slot tables |
| `tests/ranking/` | tests |

## Output record
```json
{
  "task_label": "", "host_harness": "", "none_found": false,
  "picks": [{
    "candidate_id": "", "skill_name": "", "repo": "", "skill_path": "",
    "install": {"command": "", "distribution": "repo | collection | plugin"},
    "fit": "full | partial", "missing": [""],
    "badge": "established | hidden-gem",
    "evidence_level": "verified | tested-once | inspected",
    "score": 0.0,
    "actually_does": "", "features": [""],
    "limitations": [{"text": "", "evidence": ""}],
    "claims_summary": {"supported": 0, "unsupported": 0, "unverifiable": 0, "top_unsupported": ""},
    "compatibility": {"<harness id>": {"level": "", "reasons": [""]}},
    "tested_on": ["<harness id>"],
    "requirements": {},
    "flags": ["suspicious_popularity | popular_but_unproven"],
    "sources": [""]
  }],
  "differentiator": {"signal": "", "first": 0.0, "second": 0.0},
  "set_aside": [{"candidate_id": "", "skill_name": "", "reason": ""}],
  "not_evaluated": 0,
  "display_harnesses": ["<harness id>"],
  "harness_names": {"<harness id>": "<display name>"},
  "verification_available": false
}
```
`display_harnesses` = the profiles' `default_display`, plus the host if missing. `verification_available` = the host has a verified `verification_runner`.

`evidence_level`: `verified` = verification `status: confirmed`; `tested-once` = `status: single`; `inspected` = evaluation only. A candidate with no evaluation cannot be a pick, because fit needs evaluation fields.

## Done when
- Golden-set tasks: an acceptable pick is #1 in ≥ 80%, and a `must_not_rank_first` skill is #1 in ≤ 5%.
- `good` ranks above `hype` in ≥ 85% of golden-set pairs.
- No pick is `incompatible` with the host harness. No pick has `fit: none`.
- A nonsense task returns `none_found: true` (no padding).
- A seeded 7-day-old gem fills slot 3; a seeded hype item gets `popular_but_unproven`.
