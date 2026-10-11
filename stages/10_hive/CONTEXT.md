# 10 · hive (Layer 2)

**Release: v2.** Not part of the free launch. Start only when `PROGRESS.md` says v2 has started and `CLAUDE.md` has a monthly budget.

**Job:** the shared cache. Users' sessions read results and submit new ones, so each evaluation or test is paid for once and reused by everyone. Public read, signed write, evidence validation, consensus, privacy defaults, and the server spend cap.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/10_hive/references/threat-model.md` | all | attacks and defenses |
| `stages/10_hive/references/consensus.md` | all | agreement rules, reputation, audits |
| `stages/10_hive/references/privacy.md` | all | what is shared |
| `stages/05_clustering/CONTEXT.md` | `#process` | server-side `search()` and `nearest()` |
| `skills/skill-scout/references/evaluation-rubric.md` | `#output-schema` | validate evaluation submissions |
| `stages/07_verification/CONTEXT.md` | `#output-record` | validate verification submissions |
| `stages/08_ranking/CONTEXT.md` | `#store-interface` | the API must serve this interface |
| `stages/08_ranking/references/scoring.md` | `#signal-slots` | outcome report format |

## Process
1. Build the HTTP API behind the Store interface: `search`, `bundle` (public read), `put` (signed write).
2. Write `store_remote.py`: the `remote` backend. On the first `put`, it prints the privacy notice and needs the user's consent.
3. On every `put`: check the signature and rate limit; validate the schema; validate every evidence ref (file and line exist at `commit_sha`; issue exists). Reject on mismatch.
4. Apply consensus and reputation rules.
5. Spend ledger: log tokens and cost for every server LLM call. Alert at 80% of the budget in `CLAUDE.md`. Stop server LLM jobs at 100%. User sessions keep working on their own models.
6. Add category labels from the derived labels users submit.

## Outputs
| Path | What |
|---|---|
| `src/hive/` | API, validation, consensus, reputation, spend ledger; `schema.sql` for contributor, consensus, and ledger tables |
| `skills/skill-scout/scripts/store_remote.py` | `remote` Store backend |
| `skills/skill-scout/references/privacy-notice.md` | user-facing notice text — single home |
| `tests/hive/` | tests |

## Done when
- A repeated query is served from the cache with no new evaluation.
- A submission with a fabricated evidence ref is rejected.
- An author's evaluation of their own skill is stored but excluded from consensus.
- Two agreeing verification runs → `confirmed`. Two disagreeing runs → `disputed`, and a spot check is queued within budget.
- Server LLM jobs stop at 100% of the budget; an alert fires at 80%.
- Raw task text is never stored unless the user opted in.
