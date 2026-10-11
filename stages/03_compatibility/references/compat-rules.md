# Compatibility rules

## Levels
| Level | Meaning |
|---|---|
| `compatible` | Uses only Agent Skills spec features, and its requirements are available in that harness. |
| `partial` | Uses features this harness ignores. The core instructions still work. Reasons say what is lost. |
| `incompatible` | The core depends on a feature this harness lacks. |
| `unknown` | Not enough evidence to decide. |

Precedence: `incompatible` > `partial` > `compatible`. Use `unknown` only when no rule decides and the evidence is ambiguous. Every non-`compatible` level carries at least one reason.

## Rules
Profile flags are in `harness-profiles.json` → `supports`.

| ID | Detect | Harness lacks the flag → level |
|---|---|---|
| R1 | Claude Code extension keys: `when_to_use`, `argument-hint`, `arguments`, `disable-model-invocation`, `user-invocable`, `disallowed-tools`, `model`, `effort`, `paths`, `shell`, `background` | `partial` (`claude_code_extensions`) — metadata ignored; activation or invocation may differ |
| R2 | `context: fork` or `agent` | `partial` (`context_fork`) — runs inline, not in a subagent |
| R3 | `hooks` in frontmatter | `partial` (`hooks`) — hooks will not run. Ranking raises this to `incompatible` when the skill's evaluation lists `hooks` in `core_depends_on`. |
| R4 | `` !`command` `` injection in the body | `partial` (`body_injection`) — the agent sees the raw command, not its output |
| R5 | `$ARGUMENTS`, `$0`–`$N`, or named `$arg` substitution | `partial` (`argument_substitution`) — the agent must infer arguments from the conversation |
| R6 | `${CLAUDE_PLUGIN_ROOT}` or other `${CLAUDE_*}` paths that scripts or steps depend on | `incompatible` (`claude_code_extensions`) — paths do not resolve |
| R7 | `allowed-tools` | `partial` (`allowed_tools`) — no pre-approval; the user gets prompts |
| R8 | Body requires a tool name found in another harness's `tool_lexicon` | `partial` — that step needs a substitute. Use only lexicon entries that are verified. |
| R9 | Calls tools of a named MCP server | `incompatible` when `mcp` is false; otherwise add to `requirements.mcp_servers` |
| R10 | File references outside the skill folder (`../`) | `partial` for every harness — a single-skill install does not copy those files |
| R11 | Spec warnings: `name` ≠ folder, invalid name characters | `partial` for every harness — strict loaders may skip it |

## Requirements (not harness levels)
- Script extensions and shebangs → runtimes. `.sh` or bash-only syntax → `os: [macos, linux]` (Windows needs WSL or Git Bash). `.ps1` → `os: [windows]`. Python or Node with no OS-specific calls → `os: [any]`.
- Commands named in SKILL.md or scripts (`ffmpeg`, `docker`, `git`) → `system_tools`.
- Environment variables that look like keys (`*_API_KEY`, `*_TOKEN`) → `services`, with `paid: true` when the service is known to be paid.
- HTTP calls or `curl` → `network: true`.

## Declared compatibility
The `compatibility` frontmatter field is the author's claim. Record it and show it ("author targets Claude Code"). It never changes a level by itself. Set `declared_conflict: true` when it contradicts the rules above.
