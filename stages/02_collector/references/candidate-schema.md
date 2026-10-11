# Candidate schema

IDs, `commit_sha`, `content_hash`, and the local checkout path are defined in `CLAUDE.md`.

## Candidate record
| Field | Type | Notes |
|---|---|---|
| `candidate_id` | text, PK | see `CLAUDE.md` |
| `repo` | text | `owner/repo` |
| `skill_path` | text | folder holding `SKILL.md` |
| `skill_name` | text | frontmatter `name` |
| `description` | text | frontmatter `description` (author text — a claim, not a fact) |
| `distribution` | enum | `repo` · `collection` · `plugin` |
| `plugin_manifest` | text, null | path when `distribution = plugin` |
| `first_seen` | date | earliest commit that touched `SKILL.md` |
| `last_changed` | date | latest commit touching the skill folder |
| `commit_sha` | text | |
| `content_hash` | text | |
| `frontmatter_keys` | text[] | every key found |
| `spec_warnings` | text[] | from the membership gate |
| `files` | json | `{scripts:[], references:[], assets:[], other:[]}` |
| `duplicates` | text[] | candidate_ids collapsed into this one |
| `safety` | json | `{scanner, status: pass/warn/fail, findings[]}` |
| `status` | enum | `active` · `excluded_unsafe` |

## Reject record
| Field | Type |
|---|---|
| `location` | text (`owner/repo@path`) |
| `reason` | enum (see membership.md) |
| `detail` | text |
| `seen_on` | date |
