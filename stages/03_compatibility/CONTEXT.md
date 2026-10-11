# 03 · compatibility (Layer 2)

**Job:** for each skill, decide which coding harnesses can run it, why, and what it needs to run. This is static analysis: no execution, no LLM.

## Inputs
| Load | Section | Why |
|---|---|---|
| `stages/03_compatibility/references/compat-rules.md` | all | levels and rules |
| `skills/skill-scout/references/harness-profiles.json` | all | harness facts (owned here) |
| `stages/03_compatibility/references/fixtures.md` | all | test skills and expected levels |

## Process
1. From the local checkout, parse the frontmatter keys, the body, and the file list.
2. For each harness in the profiles, apply the rules → one level plus reasons.
3. Extract requirements: runtimes, OS, system tools, MCP servers, external services and API keys, network.
4. Record the author's `compatibility` field as a claim. Flag it when it conflicts with the evidence.
5. Verify every entry in the profiles' `unverified` lists against official docs. Update the profiles and `checked_on`.

## Outputs
| Path | What |
|---|---|
| `src/compatibility/` | checker; `schema.sql` for the compatibility table |
| `skills/skill-scout/references/harness-profiles.json` | harness facts — single home |
| `data/fixtures/compat/` | fixture skills |
| `tests/compatibility/` | tests |

## Output record
```json
{
  "candidate_id": "", "content_hash": "",
  "harness": {
    "<harness id>": {"level": "compatible | partial | incompatible | unknown",
                     "reasons": ["rule id: plain explanation"]}
  },
  "requirements": {
    "runtimes": ["python>=3.10"],
    "os": ["any | macos | linux | windows"],
    "system_tools": ["ffmpeg"],
    "mcp_servers": [],
    "services": [{"name": "", "key_env": "", "paid": true}],
    "network": true
  },
  "declared_compatibility": null,
  "declared_conflict": false
}
```
Tested results are not part of this record. They come from stage 07.

## Done when
- Every fixture produces its expected level for every default-display harness.
- 20 real skills checked by hand: ≥ 90% agreement on level per harness.
- No entries remain in any `unverified` list, or each remaining one is logged in `PROGRESS.md` with the reason.
