# 07 · verification (Layer 2)

**Job:** an opt-in test on the user's machine: does the skill measurably improve results on realistic tasks, compared with no skill, in the user's own harness?

## Inputs
| Load | Section | Why |
|---|---|---|
| `skills/skill-scout/references/verification-protocol.md` | all | test procedure (owned here) |
| `skills/skill-scout/references/evaluation-rubric.md` | `#output-schema` | tasks come from supported claims |
| `skills/skill-scout/references/harness-profiles.json` | all | `verification_runner` per harness; harness ids to record |
| `stages/06_evaluation/references/github-access.md` | `#credential-order`, `#rules` | download skill files with the user's own GitHub access |

## Process
1. Build the protocol, the runtime step, and the helper script.
2. Show a token cost estimate before any run. Run only after the user agrees.
3. Ask a second time before running a skill that contains scripts.
4. Run only in a temporary folder. Delete it after the run.
5. Offer the test only where the host harness has a verified `verification_runner`.

## Outputs
| Path | What |
|---|---|
| `skills/skill-scout/references/verification-protocol.md` | procedure, thresholds — single home |
| `skills/skill-scout/steps/05-verify.md` | runtime step |
| `skills/skill-scout/scripts/verify.py` | cost estimate, temp-folder setup, run bookkeeping |
| `tests/verification/` | tests |

## Output record
```json
{
  "candidate_id": "", "content_hash": "",
  "harness": "<harness id>", "model": "",
  "tasks": [{"prompt": "", "criteria": [""]}],
  "with_scores": [0.0], "without_scores": [0.0],
  "with_score": 0.0, "without_score": 0.0, "delta": 0.0,
  "verdict": "gain | no_measurable_gain | worse",
  "failures": [""], "side_effects": [""],
  "cost_tokens": 0, "created_at": "", "contributor_id": "",
  "status": "single | confirmed | disputed"
}
```
`status` starts as `single`. Only stage 10 consensus sets `confirmed` or `disputed`.

## Done when
- On 10 golden-set skills (5 `good`, 5 `hype` or `mediocre`), the delta direction matches the label for ≥ 8.
- The cost estimate is within ±30% of the actual tokens used.
- A skill with scripts triggers the second confirmation.
- No file is left behind outside the temporary folder.
