# Cost model (owner-side LLM spend only)

Users pay for evaluations run in their own sessions. In v1, the owner pays for one thing only:

| Job | When | How |
|---|---|---|
| Seeding | once, before launch: stage 06 evaluation of the golden set plus the top candidates in the most likely categories | owner's Claude Code subscription ($0), or the smallest capable API model within the v1 seeding budget in `CLAUDE.md` |

v1 has no recurring LLM jobs. Spot checks, audits, and external report classification start in v2 (stages 10–11).

## Estimator
`seeding_cost = evaluations × tokens_per_evaluation × price_per_token`

- Take `tokens_per_evaluation` from stage 06's evidence budget plus prompt and output size.
- Read current prices from the provider's pricing page when you run the estimator. Do not hardcode prices.
- Output: cost per evaluation, and how many evaluations fit the seeding budget. Seed the golden set first, then the highest pre-score candidates per category until the budget is used.
