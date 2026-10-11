# Sources

## Discovery
- GitHub code search for files named `SKILL.md`.
- GitHub topics: `agent-skills`, `claude-skills`, `claude-code-skills`, `codex-skills`, `gemini-skills`, `antigravity-skills`.
- Known collections: `anthropics/skills`, `openai/skills`, `vercel-labs/agent-skills`, `github/awesome-copilot`, `huggingface/skills`.
- Curated lists (follow their links to the real repos): `VoltAgent/awesome-agent-skills`.
- Seed list: public catalog exports, e.g. `dmgrok/agent-plugins` `catalog.json` (MIT). Check the license of any other source before use.

## Soft signals only
- Registry install counts (e.g. skills.sh), if a public API or export exists and its terms allow use. Stage 04 treats these as a tiebreaker only.

## Whose token
The scheduled build uses the owner's token from the repository secret `AF_GITHUB_TOKEN`. It is never shipped in the skill, the index, or any log. One build serves every user, so the number of users does not change its API use. Users' own GitHub calls follow `stages/06_evaluation/references/github-access.md` (a later stage; listed here for orientation only).

## Rate limits
- Authenticate every GitHub call. REST allows 5,000 requests per hour; search endpoints have a stricter separate limit.
- On a limit response: back off, save the cursor, resume. Never drop work silently.
