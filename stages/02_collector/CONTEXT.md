# 02 · collector (Layer 2)

**Job:** find every public agent skill, keep only real skills, drop unsafe ones and duplicates, and store one candidate record per skill folder.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/02_collector/references/membership.md` | all | what counts as an agent skill |
| `stages/02_collector/references/sources.md` | all | where to look; rate limits |
| `stages/02_collector/references/candidate-schema.md` | all | records to write |

## Process
1. Discover skill folders from the sources.
2. Apply the membership gate. Log every reject with a reason.
3. Safety gate: run an existing agent-skill security scanner (reuse one; check its license). Fail → exclude and record findings.
4. Dedupe: same `content_hash` → one canonical candidate (earliest first commit). Forks and mirrors collapse into their source.
5. Check out each accepted skill to its local checkout path (see `CLAUDE.md`).
6. Store candidate and reject records.
7. Schedule: daily sweep for new skills (see `CLAUDE.md`); weekly full refresh.

## Outputs
| Path | What |
|---|---|
| `src/collector/` | discovery, gates, dedupe, scheduler; `schema.sql` for candidate and reject tables |
| `src/db/core/` | DB connection and a migration runner that applies every `src/*/schema.sql` |
| `tests/collector/` | tests |

## Done when
- The daily job stores ≥ 1,000 candidates.
- Manual sample of 100 rejects: < 5% are real skills wrongly rejected.
- Manual sample of 100 accepts: < 5% are not real skills.
- A seeded fork collapses into its source.
