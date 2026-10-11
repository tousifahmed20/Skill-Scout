# Consensus

## States (per candidate and `content_hash`)
`unverified` → `single` → `confirmed` (≥ 2 independent, agreeing) or `disputed` (disagreement beyond tolerance)

## Agreement
| Record | Agree when |
|---|---|
| Evaluation | Credibility (stage 08 formula) within 0.15, and the same verdict on ≥ 80% of core claims |
| Verification | Same verdict, and `delta` within 0.15 |

"Independent" = different contributors, neither linked to the skill's repo, both above the reputation threshold.

## Reputation
- New keys start low. An optional GitHub link raises the starting value. It is never required.
- Agreeing with consensus or a spot check → up. Disagreeing → down. Repeated rejects → submissions held for review.

## Server checks (within the budget)
- Every `disputed` record → one spot check.
- A random ~2% of accepted submissions → re-evaluated.
