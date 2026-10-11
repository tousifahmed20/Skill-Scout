# Competitive landscape (for humans)

Snapshot: 11 October 2026. Re-check before launch — this space moves weekly.

## Who exists and what they rank on

| Product | What it ranks on | Tests real behavior? |
|---|---|---|
| **skills.sh** (Vercel) | Anonymous, deduplicated install telemetry from its CLI; partner security audits; says it can't guarantee skill quality | No |
| **Skillselion** | All-time installs from the skills.sh registry; tracks ~59k skills | No |
| **dmgrok/agent-plugins** (formerly agent_skills_directory) | 0–100 score: maintenance recency (50), presence of scripts/references/assets folders (30), official vs. community provider (20); static secrets/injection checks; offline project-matching suggestions | No |
| **linny006/awesome-agent-skills** | README says it crawls, tests and rates daily, but its documented pipeline only pulls GitHub Search API results every 15 minutes and rewrites a table (stars, language, date). Its list includes repos that aren't skills | No — and a live example of the README-vs-reality gap we're built to catch |
| **SkillRank** | GitHub API metadata (stars, forks, topics, dates) plus editorial curation | No |
| **SkillSync** (Chumaniac) | Offline provenance, compatibility and change checks for a local skill; explicitly does not execute it. Alpha, 0 stars | No — verifies integrity, not behavior |
| **Agentic Skills Evaluation Framework** (research) | Generates tasks from ~500 real skills; runs 19 agent-model setups with and without the skill; measures the gain | **Yes** — but a research benchmark, not a finder |
| **Vals SkillsBench** | Benchmarks models on skill-related tasks | About models, not which skill to pick |

## The gap

- Consumer tools measure **popularity, maintenance, folder structure, and security**.
- None tells a user *"this skill measurably improves results for your task."*
- Research proves the with/without method works. Nobody has productized it — because per-skill testing costs tokens. The BYO-model Hive is exactly what amortizes that cost.

## Our position

**The finder that checks whether a skill actually works — and where it works.** Evidence over marketing; behavior-tested where possible; harness compatibility on every pick; new gems surfaced before they're famous.

## Threats

- skills.sh (largest install base) could add verification.
- dmgrok could add LLM evaluation to its scoring.
- **Moat:** the accumulated verification data in the Hive, plus a reputation for honesty (including "No measurable gain" verdicts).

## Reuse, don't rebuild

- Registry install counts → Soft-tier signal (stage 04)
- Existing agent-skill security scanners (e.g. NVIDIA SkillSpector — check license and fit) → safety gate (stage 02)
- Public catalog JSON exports → collector seed list (stage 02)
- vercel-labs/skills README → harness paths and feature support (stage 03)

## Sources

- [skills.sh — About](https://skills.sh/about) · [Docs](https://skills.sh/docs)
- [Skillselion](https://skillselion.com/skills)
- [dmgrok/agent-plugins](https://github.com/dmgrok/agent-plugins)
- [linny006/awesome-agent-skills](https://github.com/linny006/awesome-agent-skills)
- [SkillRank methodology](https://skillrank.it.com/methodology)
- [Chumaniac/skillsync](https://github.com/Chumaniac/skillsync)
- [Agentic Skills Evaluation Framework](https://benchmarklist.com/benchmarks/agentic_skills_evaluation_framework/)
- [Vals SkillsBench (via BenchLM)](https://benchlm.ai/md/benchmarks/skillsbench.md)
- [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) — large curated list (static)
