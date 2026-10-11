# Verification protocol

## What this measures
Whether giving the agent this skill improves its results on realistic tasks. The skill's files are provided to the agent directly, so this does not test whether the harness would trigger the skill on its own.

## Procedure
1. Take the `supported` claims (core first) from the skill's evaluation. Write 3 realistic tasks that exercise them. For each task, write 3–5 pass/fail criteria.
2. **Baseline:** run each task in a fresh agent context without the skill.
3. **Treatment:** run each task in a fresh agent context with the skill's files available in the temporary folder and its SKILL.md given as instructions.
4. **Blind judge:** in a separate context, show both outputs for a task as A and B in random order. Score each 0–1 against the criteria. The judge is not told which output used the skill.
5. `delta = mean(with) − mean(without)`.

## Verdicts
| Verdict | Rule |
|---|---|
| `gain` | `delta > 0.05` |
| `no_measurable_gain` | `−0.05 ≤ delta ≤ 0.05` |
| `worse` | `delta < −0.05` |

Report `no_measurable_gain` and `worse` plainly. They are useful, honest results.

## Safety
- Temporary folder only. Never the user's project folder.
- No network writes unless a task needs them and the user agreed.
- A skill with scripts needs a second, explicit confirmation.
