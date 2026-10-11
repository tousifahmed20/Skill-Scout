# GitHub access on the user's machine

Applies to every skill script that calls GitHub on the user's machine (`fetch_evidence.py`, `verify.py`). The scheduled build is separate: it uses the owner's token from a repository secret (stage 02) and never ships it.

## Credential order
`github_auth.py` uses the first source that works:
1. Environment variable `SKILL_SCOUT_GITHUB_TOKEN`.
2. `github_token` in `~/.skill-scout/config.json`.
3. Environment variables `GH_TOKEN`, then `GITHUB_TOKEN`.
4. GitHub CLI login: `gh auth token`, when `gh` is installed and signed in.
5. Git's saved GitHub login: `git credential fill` for `https://github.com` — only after the user agrees once. Store the answer as `allow_git_credentials` in `config.json`.
6. Nothing found → anonymous. GitHub allows 60 API requests per hour per IP address.

Coding harnesses do not hand their built-in GitHub connections to skill scripts. Sources 4 and 5 are the logins most harnesses use for GitHub work, so they are usually the login the user already has.

Commands:
- `github_auth.py status` prints `authenticated (<source>)` or `anonymous`, plus the remaining quota. It never prints the token.
- `github_auth.py init` creates `~/.skill-scout/config.json` with an empty `github_token` and prints the file path, so the user can add a token in a text editor.

## Rules
- Never ask the user to paste a token into the chat. It would enter the model's context and the transcript. Point them to `references/github-setup.md`.
- Send the token only to `api.github.com`. Never print, log, cache, or store it anywhere else, including `local.sqlite` and result files.
- Read-only calls only.
- Create `config.json` readable by the user only, where the OS supports it.

## Call budget
Keep API use low, so anonymous access is enough for normal queries:
- File contents: `raw.githubusercontent.com` at the pinned `commit_sha` (not counted against the REST API limit).
- File tree: 1 API call (git trees endpoint).
- Issues that mention the skill: at most 2 API calls.

Target: ≤ 3 API calls per candidate, about 15 for a query that evaluates 5 candidates.

## When the limit is reached
Stop fetching. Finish ranking with the candidates already evaluated, report how many were skipped, and show `references/github-setup.md`.
