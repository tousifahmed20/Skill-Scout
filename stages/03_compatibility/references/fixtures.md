# Fixtures

Build one minimal skill per row in `data/fixtures/compat/<id>/`. Expected levels are for the default-display harnesses.

| Fixture | Contains | claude-code | Others in default display |
|---|---|---|---|
| `portable` | spec fields only, plain steps | compatible | compatible |
| `cc-keys` | `argument-hint`, `disable-model-invocation` | compatible | partial (R1) |
| `fork` | `context: fork` | compatible | partial (R2) |
| `hooks` | `hooks` | compatible | partial (R3) |
| `injection-cmd` | `` !`git status` `` in body | compatible | partial (R4) |
| `arguments` | `$ARGUMENTS` | compatible | partial (R5) |
| `plugin-root` | script path via `${CLAUDE_PLUGIN_ROOT}` | compatible | incompatible (R6) |
| `allowed-tools` | `allowed-tools: Read` | compatible | partial (R7) where `allowed_tools` is false; compatible elsewhere |
| `outside-ref` | links `../shared/guide.md` | partial (R10) | partial (R10) |
| `name-mismatch` | `name` ≠ folder | partial (R11) | partial (R11) |
| `bash-script` | `scripts/run.sh` | compatible; `os: [macos, linux]` | same |
| `paid-api` | uses `OPENAI_API_KEY` | compatible; `services` has a paid entry | same |
