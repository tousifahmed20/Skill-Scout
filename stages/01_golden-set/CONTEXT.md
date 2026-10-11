# 01 · golden-set (Layer 2)

**Job:** build the hand-labeled set that every scoring change is tested against, and the seeding cost estimate.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/01_golden-set/references/labeling-guide.md` | all | label definitions and file formats |
| `stages/01_golden-set/references/cost-model.md` | all | what seeding covers and how to estimate it |

## Process
1. Pick 6–8 task categories people are likely to ask for (for example: UI/design, code review, testing, docs, deployment, video/YouTube automation, data analysis, research).
2. For each category, pick 5–6 real agent skills. Include on purpose: at least one famous-but-weak and one new-but-good per category where they exist. Target about 40 skills.
3. Label each skill per the labeling guide, with a written reason and evidence links.
4. For each category, write 2 realistic one-sentence tasks with acceptable picks and must-not-be-first picks.
5. Build the cost estimator per the cost model.

## Outputs
| Path | What |
|---|---|
| `data/golden-set/golden_set.json` | labeled skills |
| `data/golden-set/tasks.json` | test tasks with expected picks |
| `src/cost/` | cost estimator |

## Done when
- About 40 skills labeled, each with a reason and at least one evidence link.
- Each category has at least one `good` and one `hype` or `mediocre` label.
- 12–16 tasks written, each with ≥ 1 acceptable pick.
- The estimate shows how many evaluations fit the seeding budget in `CLAUDE.md`.
