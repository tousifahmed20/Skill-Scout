# Skill Scout — build workspace (Layer 0)

## What this is
A cross-harness Agent Skill. The user describes a task in one sentence. The skill returns up to 3 of the best existing **agent skills** for that task, with evidence, limitations, sources, and the coding harnesses each skill works in.

## Global invariants (single home — other files point here, never copy)
- **Scope:** agent skills only — a folder containing a `SKILL.md` in the Agent Skills format. Not MCP servers, subagent definitions, CLAUDE.md/AGENTS.md packs, apps, or libraries. Exact rules: `stages/02_collector/references/membership.md`.
- **Answer:** at most 3 picks, never padded. Popularity alone never decides #1.
- **Compatibility:** every pick shows which coding harnesses it works in.
- **Safety:** never execute third-party skill code on our servers. Behavioral tests run only on the user's machine, opt-in.
- **Models and logins:** the user's own model does evaluation inside their agent session, and the user's own GitHub access does their GitHub calls. We never hold user keys or tokens. The owner's GitHub token is used only by the scheduled build.
- **Budget (v1, free launch):** no recurring charges of any kind. One-time seeding LLM spend ≤ $5, or $0 when the owner seeds with their own Claude Code subscription. No server LLM jobs. v2 sets a monthly cap here before stage 10 starts.
- **Releases:** v1 = stages 01–09, with no server: GitHub Actions builds the index and GitHub Releases hosts it. v2 = stages 10–11 (shared cache, external signals).
- **Build harness:** Claude Code. The repo works locally and on GitHub.

## IDs and locators (single home)
- `candidate_id` = `<owner>/<repo>@<skill_path>` — `skill_path` is the repo-relative folder that holds `SKILL.md`.
- `commit_sha` = the commit a record was computed from.
- `content_hash` = sha256 over every file in the skill folder (paths sorted, LF line endings). Any change → every cached record for that skill is stale.
- Local checkout = `data/cache/skills/<owner>__<repo>/<commit_sha>/<skill_path>/` (gitignored).
- Harness ids = the `id` values in `skills/skill-scout/references/harness-profiles.json`.
- New skill = `first_seen` ≤ 14 days ago. Collection (02), health refresh (04), and the Hidden Gem engine (08) all use this window.
- Pipeline DB = `data/index/skill-scout.sqlite` (gitignored). Published each run as the GitHub Release asset `index.sqlite.gz`; latest copy at `https://github.com/tousifahmed20/Skill-Scout/releases/latest/download/index.sqlite.gz` (baked into `store.py` as `DEFAULT_INDEX_URL`).
- Skill cache on the user's machine = `~/.skill-scout/index.sqlite` (downloaded index), `~/.skill-scout/local.sqlite` (the user's own new results), and `~/.skill-scout/config.json` (user settings, including an optional GitHub token).
- Each module runs as `python -m src.<module>`.

## Map
| Path | What | Layer |
|---|---|---|
| `CONTEXT.md` | routing table: task → stage | 1 |
| `PROGRESS.md` | active stage, results, open issues, route changes | state |
| `stages/NN_name/CONTEXT.md` | stage contract: Inputs, Process, Outputs, Done when | 2 |
| `stages/NN_name/references/` | stable rules for that stage | 3 |
| `skills/skill-scout/` | the shipped skill, assembled from stage outputs | product |
| `src/`, `tests/`, `data/` | code, tests, data (created by stages) | product |
| `tools/check_routes.py` | validates routes and ownership | tool |
| `docs/` | human "why" documents — do not read unless the user asks | human |

## Stack (single home — change only with an entry in `docs/decisions.md`)
- **Language:** Python 3.11+ everywhere. Use `pathlib` for paths; the owner develops on Windows, so no bash-only tooling in the repo.
- **Shipped skill scripts** (`skills/skill-scout/scripts/`): standard library only, so users install nothing. Server and dev code may use packages.
- **Database (v1):** SQLite (standard library) for the pipeline and the published index. Write every `schema.sql` in SQLite SQL. v2 moves the shared cache to Postgres + pgvector.
- **Embeddings:** a small open-source sentence-transformers model on CPU, run only inside GitHub Actions. Stage 05 picks and records the exact model. The skill never embeds; it searches text.
- **Scheduled jobs and hosting (v1):** GitHub Actions cron (free for public repos) builds the index; GitHub Releases hosts it. No other server.
- **Hive API (v2):** Python HTTP API (FastAPI). Host choice is open in `PROGRESS.md`.
- **Tests:** pytest. **Dependencies:** `pyproject.toml`.
- **Security scanning:** reuse an existing agent-skill scanner (stage 02). Do not build one.

## Session protocol
1. Read `PROGRESS.md`, then `CONTEXT.md`.
2. Work in one stage. Read its `CONTEXT.md`. Load only the files in its Inputs table, and only the sections named there.
3. Do not open other stage folders or `docs/`.
4. Missing a fact? Stop. Add the exact path and `#section` to the stage's Inputs table, run `python tools/check_routes.py`, then read it. Log the change under "Route changes" in `PROGRESS.md`.
5. Before ending: update `PROGRESS.md` (what changed, Done-when results, next step).

## Conventions
- Folders and files are lowercase-hyphenated. Stages are `NN_name`. Root system files are UPPERCASE.
- One fact, one home. Point to it; never copy it.
- Reads go one way: a stage reads its own folder and lower-numbered stages only.
- Each file has exactly one owner stage (see the Outputs tables). Each module owns its own `schema.sql` and `tests/<module>/`.
- Routing files hold routes only — no reference content.
- Never use `@path` imports in this file or any `CONTEXT.md`: Claude Code loads imports at launch, which defeats routing. Write paths in backticks.
- Machine files say what. `docs/` says why.
- The shipped skill must stay portable: spec frontmatter fields only, no harness-specific syntax.
