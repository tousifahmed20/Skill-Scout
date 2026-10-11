-- Stage 02 (collector) owns these tables. SQLite. Idempotent.
-- Field meanings: stages/02_collector/references/candidate-schema.md
-- List/json fields are stored as JSON text (SQLite has no array type).

CREATE TABLE IF NOT EXISTS candidate (
    candidate_id     TEXT PRIMARY KEY,          -- <owner>/<repo>@<skill_path>
    repo             TEXT NOT NULL,             -- owner/repo
    skill_path       TEXT NOT NULL,             -- folder holding SKILL.md
    skill_name       TEXT NOT NULL,             -- frontmatter name
    description      TEXT,                       -- frontmatter description (a claim)
    distribution     TEXT NOT NULL CHECK (distribution IN ('repo','collection','plugin')),
    plugin_manifest  TEXT,                       -- set when distribution = plugin
    first_seen       TEXT,                       -- earliest commit touching SKILL.md (ISO date)
    last_changed     TEXT,                       -- latest commit touching the folder (ISO date)
    commit_sha       TEXT,
    content_hash     TEXT NOT NULL,
    frontmatter_keys TEXT NOT NULL DEFAULT '[]', -- json array
    spec_warnings    TEXT NOT NULL DEFAULT '[]', -- json array
    files            TEXT NOT NULL DEFAULT '{}', -- json {scripts,references,assets,other}
    duplicates       TEXT NOT NULL DEFAULT '[]', -- json array of collapsed candidate_ids
    safety           TEXT NOT NULL DEFAULT '{}', -- json {scanner,status,findings}
    status           TEXT NOT NULL CHECK (status IN ('active','excluded_unsafe'))
);
CREATE INDEX IF NOT EXISTS idx_candidate_hash ON candidate(content_hash);
CREATE INDEX IF NOT EXISTS idx_candidate_repo ON candidate(repo);

CREATE TABLE IF NOT EXISTS reject (
    location  TEXT PRIMARY KEY,                  -- owner/repo@path
    reason    TEXT NOT NULL,                     -- see membership.md
    detail    TEXT,
    seen_on   TEXT NOT NULL                      -- ISO date
);

-- Resumable sweep cursor: on a rate-limit/crash the pipeline reloads the
-- remaining queue so work is never dropped silently (sources.md).
CREATE TABLE IF NOT EXISTS sweep_state (
    sweep     TEXT PRIMARY KEY,                  -- 'daily' | 'full'
    queue     TEXT NOT NULL DEFAULT '[]',        -- json: repos not yet swept
    done      TEXT NOT NULL DEFAULT '[]',        -- json: repos completed this sweep
    updated   TEXT
);
