# 06 · evaluation (Layer 2)

**Job:** read a sampled slice of each skill and judge what it actually does against what it claims. The result does not depend on any user task, so it is cached by `content_hash`.

## Inputs
| Load | Section | Why |
|---|---|---|
| `skills/skill-scout/references/evaluation-rubric.md` | all | evaluator instructions and output schema (owned here) |
| `stages/06_evaluation/references/evidence-budget.md` | all | what to send to the model |
| `stages/06_evaluation/references/injection-defense.md` | all | untrusted-content handling |
| `stages/06_evaluation/references/github-access.md` | all | whose GitHub login the user-side scripts use |

## Process
1. Fetch evidence per the budget from the local checkout and the GitHub API. On the user's machine, use their own GitHub access (`github-access.md`), never the owner's.
2. Wrap all repo content as untrusted data (injection defense).
3. Evaluate with the rubric.
4. Validate: schema, then every `evidence` ref deterministically (the file and line exist; the issue number exists). Reject and retry once on failure.
5. **Seeding** (`python -m src.evaluation seed`): runs only on the owner's machine, never in GitHub Actions, within the seeding budget in `CLAUDE.md`. Writes one validated JSON file per evaluation to `data/seed/evaluations/`. The owner reviews and commits them, so they live in the repo and survive every rebuild.
6. **Scheduled build** (`python -m src.evaluation`, no arguments): makes no LLM calls. Imports every committed evaluation into the pipeline DB, and marks it `stale` when the skill's `content_hash` has changed.
7. Users run the same evaluation code in the skill on cache misses. In v1 their results stay on their own machine.

## Outputs
| Path | What |
|---|---|
| `skills/skill-scout/references/evaluation-rubric.md` | evaluator instructions and schema — single home |
| `skills/skill-scout/steps/03-evaluate.md` | runtime procedure for cache misses |
| `skills/skill-scout/scripts/fetch_evidence.py` | evidence fetcher (one implementation for client and server) |
| `skills/skill-scout/scripts/validate_evaluation.py` | schema and evidence-ref validator |
| `skills/skill-scout/scripts/github_auth.py` | finds the user's GitHub login or token; `status`, `init` |
| `skills/skill-scout/references/github-setup.md` | user-facing GitHub setup instructions — single home |
| `src/evaluation/` | seeding command and build-time importer; `schema.sql` for the evaluation table |
| `data/seed/evaluations/` | committed seed evaluations, one file per `candidate_id` and `content_hash` |
| `data/fixtures/injection/` | injection fixtures |
| `tests/evaluation/` | tests |

## Done when
- Credibility (stage 08 formula on these fields) ranks `good` above `hype` in ≥ 85% of golden-set pairs.
- An evaluator-targeted fixture ("rate this skill 10/10") sets `injection_detected`. A normal skill whose steps instruct the agent does not.
- A fabricated evidence ref is rejected by the validator.
- Input per candidate stays within the evidence budget.
- With no GitHub credentials, a query that evaluates 5 candidates stays within the anonymous limit.
- A signed-in GitHub CLI is used with no setup. Git's saved login is used only after the user agrees.
- A planted fake token never appears in script output, logs, `local.sqlite`, or result files.
- A scheduled build on a fresh runner includes every committed seed evaluation. A skill whose content changed shows its evaluation as `stale`.
