# Skill Scout

An agent skill that finds the best existing agent skills for a task. Describe the task in one sentence; get up to 3 picks with what each skill actually does, its limitations, claim checks, test status, sources, and the coding harnesses it works in.

**Status:** v1 (stages 01–09) built and tested — 90 tests pass, routes clean. Going live (create the public repo, seed evaluations, run the first scheduled build) is pending; the exact steps are in `PROGRESS.md` under "Going live". v2 (stages 10–11: shared cache, external signals) is not started.

**Cost model:** v1 is free to run — no server, no recurring charges. GitHub Actions builds the skill index and GitHub Releases hosts it. Users' own models do all evaluation.

## Working on this repo with Claude Code
1. Open this folder in Claude Code.
2. Say: "Continue from PROGRESS.md."

Claude Code loads `CLAUDE.md` automatically. That file sends it to `CONTEXT.md`, which routes each task to one stage folder. Each stage's `CONTEXT.md` lists exactly what to read. Run `python tools/check_routes.py` after changing any route.

## Layout
```
CLAUDE.md            Layer 0 — what this is, global rules, IDs, map
CONTEXT.md           Layer 1 — routing table: task → stage
PROGRESS.md          state — active stage, results, open issues
stages/NN_name/      Layer 2 contract (CONTEXT.md) + Layer 3 rules (references/)
skills/skill-scout/ the shipped skill
src/ tests/ data/    code, tests, data (created during the build)
tools/               route checker
docs/                human docs — why, not what
```

## Run it
- **Build the index** (server side, Python 3.11+): `pip install pyyaml "sentence-transformers>=3"`, then run the modules in stage order — `python -m src.collector`, `compatibility`, `health`, `clustering`, `evaluation`, `ranking gem`. In CI this is `.github/workflows/build-index.yml`, which publishes `index.sqlite.gz` as a GitHub Release. Tests: `python -m pytest`; routes: `python tools/check_routes.py`.
- **The shipped skill** lives in `skills/skill-scout/` and runs on the standard library only — its scripts (`rank.py`, `store.py`, `fetch_evidence.py`, …) read the downloaded index and need no install. `SKILL.md` is the router; it loads one step file at a time.

## GitHub
The skill lives at [tousifahmed20/Skill-Scout](https://github.com/tousifahmed20/Skill-Scout). Users install it with the `skills` CLI:

```bash
npx skills add tousifahmed20/Skill-Scout --skill skill-scout
```
