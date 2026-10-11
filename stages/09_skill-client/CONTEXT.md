# 09 · skill-client (Layer 2)

**Job:** assemble the shipped skill — a short router plus step files that load only when needed — publish the index for free, and prove it end to end in Claude Code, then Codex, then Gemini CLI and Antigravity.

## Inputs
| Load | Section | Why |
|---|---|---|
| `skills/skill-scout/references/harness-profiles.json` | all | host detection (`detect_env`), names, `default_display` |
| `stages/03_compatibility/CONTEXT.md` | `#output-record` | compatibility levels to display |
| `stages/06_evaluation/CONTEXT.md` | `#outputs` | evaluate step and rubric file names |
| `stages/07_verification/CONTEXT.md` | `#outputs` | verify step and protocol file names |
| `stages/08_ranking/CONTEXT.md` | `#outputs`, `#output-record`, `#store-interface` | `rank.py` commands, answer fields, `Store.put` |
| `stages/08_ranking/references/scoring.md` | `#signal-slots` | outcome report format |

## Process
1. Write `SKILL.md` as a router: a table of steps, what each loads, and when. Keep it under 100 lines. Use spec frontmatter fields only, so the skill itself stays portable.
2. Write steps 2, 6, 7, the output template, and `detect_harness.py`.
3. **Free publishing:** write the GitHub Actions workflow. On schedule it runs each module in stage order (`python -m src.<module>`, see `CLAUDE.md`), compresses the pipeline DB, and publishes it as the release asset named in `CLAUDE.md`. Keep only the last 7 releases. Add a short weekly commit (for example a `data/index/last-build.txt` stamp), because GitHub pauses scheduled workflows in public repos after 60 days with no repository activity.
4. Run the golden-set tasks through the skill in Claude Code. Then repeat in Codex and Gemini CLI or Antigravity.
5. Check the read set on a cache-hit query: only `SKILL.md`, `steps/02-retrieve.md`, `steps/04-fit-rank.md`, `steps/06-answer.md`, and the output template load.

## Outputs
| Path | What |
|---|---|
| `skills/skill-scout/SKILL.md` | router — entry point |
| `skills/skill-scout/steps/02-retrieve.md` | runtime step |
| `skills/skill-scout/steps/06-answer.md` | runtime step |
| `skills/skill-scout/steps/07-share.md` | runtime step |
| `skills/skill-scout/references/output-template.md` | answer format — single home |
| `skills/skill-scout/scripts/detect_harness.py` | prints the host harness id or `unknown` |
| `.github/workflows/build-index.yml` | scheduled pipeline and release publishing |
| `data/index/last-build.txt` | weekly activity stamp |
| `tests/skill-client/` | end-to-end tests and transcripts |

## Done when
- Golden-set tasks through the skill in Claude Code meet stage 08's accuracy bar.
- Codex and Gemini CLI or Antigravity give the same #1 on ≥ 90% of the tasks where Claude Code's #1 is `compatible` with that harness.
- Every answer matches the output template, and every pick shows compatibility for the default-display harnesses.
- The cache-hit read set matches step 5 of the Process.
- A fresh machine with only Python installed downloads the index from GitHub Releases and answers a query. No account, server, or package install is needed.
- Running cost: $0 per month (GitHub Actions on a public repo, GitHub Releases, no other services).
- The skill passes `skills-ref validate`, and its `name` matches its folder.
