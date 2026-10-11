# Membership gate

Membership answers one question: **is this a real agent skill?** It does not judge quality, popularity, or maintenance. Those are later stages.

## Accept — all must hold
1. The folder contains a file named exactly `SKILL.md`. (Lowercase `skill.md` does not load on case-sensitive systems → reject with reason `wrong_filename`.)
2. The YAML frontmatter parses.
3. `name` and `description` exist and are non-empty.
4. The body has real instructions: at least 5 non-template lines. Template placeholders ("TODO", "Describe your skill here") do not count. Tune the line threshold against the reject sample.

The folder can live anywhere in a public repo: repo root, `skills/`, `.claude/skills/`, `.agents/skills/`, `.github/skills/`, or a plugin's `skills/` folder. If it is inside a plugin, set `distribution: plugin` and record the plugin manifest path.

## Record as warnings, do not reject
Stage 03 uses these to judge compatibility.
- `name` does not match the folder name, or breaks the spec character rules.
- `description` longer than 1,024 characters.
- `SKILL.md` longer than 500 lines.
- Frontmatter keys outside the spec (`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`).
- File references that point outside the skill folder (`../`).

## Reject — with reason
| Reason | Case |
|---|---|
| `no_skill_md` | No `SKILL.md` in the folder |
| `wrong_filename` | `skill.md` or another casing |
| `bad_frontmatter` | Missing, unparseable, or no `name`/`description` |
| `placeholder` | Body below the instruction threshold |
| `out_of_scope` | MCP server, subagent definition (`.claude/agents/*.md`), CLAUDE.md/AGENTS.md/rules packs, awesome-lists, apps, or libraries with no `SKILL.md` |

An app or CLI repo that also ships a `SKILL.md` is accepted. The skill folder is the candidate; the app becomes a requirement in stage 03.

## Not membership questions
Archived repo, low stars, no license, old commits → keep the candidate. Stage 04 records these as health signals.
