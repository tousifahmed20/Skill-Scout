# Labeling guide

## Labels
| Label | Meaning |
|---|---|
| `good` | Does what it claims; instructions are specific; you would recommend it for its task. |
| `mediocre` | Works partly, or is too generic to beat a plain prompt. |
| `hype` | Claims clearly exceed what its files do, or popularity far exceeds substance. |

## Rules
- Judge the skill folder (SKILL.md, scripts, references), not the README pitch and not the star count.
- Try the skill in a harness when you can. Record which one in `harness_tried`.
- Record `commit_sha`. Skills change; a label is only valid for the commit you judged.
- One reason sentence per skill, pointing at evidence (file and line, or issue number).

## `golden_set.json` record
```json
{
  "candidate_id": "owner/repo@path/to/skill",
  "commit_sha": "",
  "category": "",
  "label": "good | mediocre | hype",
  "reason": "",
  "evidence": ["https://github.com/..."],
  "harness_tried": ["claude-code"],
  "labeled_on": "YYYY-MM-DD"
}
```

## `tasks.json` record
```json
{
  "task": "one sentence, as a user would type it",
  "category": "",
  "host_harness": "claude-code",
  "acceptable_picks": ["candidate_id"],
  "must_not_rank_first": ["candidate_id"]
}
```
