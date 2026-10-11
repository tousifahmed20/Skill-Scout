# Product overview (for humans)

## Problem
Tens of thousands of agent skills are published, and many READMEs are LLM-written marketing. Directories rank skills by installs, update recency, folder structure, or security scans. None checks whether a skill does what it claims (see `competitive-landscape.md`). People pick by stars, install the wrong thing, and lose time. They also can't easily tell whether a skill will even work in their coding tool.

## What it does
Inside their coding agent, the user says something like "I need something that turns long YouTube videos into captioned Shorts." The skill answers with up to 3 picks. Each pick shows:
- what it actually does, from its files rather than its README
- how well it fits the task (full, or partial with what's missing)
- strengths, and limitations with sources
- a claims check: supported, unsupported, unverifiable
- which coding harnesses it works in, and why it doesn't work in the others
- what it needs: runtimes, OS, tools, paid API keys
- whether it was behavior-tested, and on which harness

## Why it's different
1. **Behavioral verification.** An opt-in with/without test of whether a skill measurably helps. Research uses this method; no consumer tool offers it.
2. **Evidence over marketing.** README text is a claim to check, not a fact.
3. **Harness compatibility.** Every pick says where it works, with reasons.
4. **Hidden Gem slot.** Good new skills can surface before they're popular.
5. **Hive cache.** Each evaluation or test is paid for once, by one user's own model, and reused by everyone.

## Release plan and cost
| Release | Stages | What runs where | Cost to the owner |
|---|---|---|---|
| v1 — free launch | 01–09 | GitHub Actions builds the index on a schedule; GitHub Releases hosts it; the skill downloads it; users' own models evaluate anything not yet checked, and those results stay on their machine | one-time seeding ≤ $5 (or $0 with the owner's Claude Code subscription); **$0 per month** |
| v2 — shared cache | 10–11 | a small server shares users' results with everyone; external reports from Hacker News and Reddit | a monthly budget set before v2 starts |

Move to v2 when users keep re-checking the same skills on their own machines, or when shared results would clearly improve answers.

## Non-goals (v1)
- Recommending anything that is not an agent skill (MCP servers, subagent definitions, apps).
- Email or newsletter delivery.
- Running third-party skill code on our servers.
- Paid placement, ever.

## Success measures
Each stage's "Done when" holds the exact bars. Headline measures:
- An acceptable skill is #1 on ≥ 80% of golden-set tasks; a known-hype skill is #1 on ≤ 5%.
- No pick is incompatible with the user's harness.
- Users report "it worked" on #1 picks (tracked through outcome reports).
- v1 runs at $0 per month; seeding stays within its one-time budget.
