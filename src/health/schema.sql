-- Stage 04 (health-signals) owns this table. SQLite. Idempotent.
-- Field meanings: stages/04_health-signals/references/signals.md
-- Raw values only; stage 08 normalizes and weights them.
-- content_hash + computed_at drive the refresh cadence (CLAUDE.md: weekly,
-- daily for new skills). Scope and flags are JSON text.

CREATE TABLE IF NOT EXISTS health (
    candidate_id               TEXT PRIMARY KEY,
    content_hash               TEXT,                    -- candidate.content_hash this was computed from
    computed_at                TEXT,                    -- ISO datetime

    independent_issue_reports  INTEGER NOT NULL DEFAULT 0,
    linked_fix_closures        INTEGER NOT NULL DEFAULT 0,
    closed_without_fix         INTEGER NOT NULL DEFAULT 0,
    substantive_commits_90d    INTEGER NOT NULL DEFAULT 0,
    median_diff_lines          INTEGER NOT NULL DEFAULT 0,
    contributors               INTEGER NOT NULL DEFAULT 0,
    independent_contributors   INTEGER NOT NULL DEFAULT 0,
    maintainer_first_response_h REAL,                   -- null when not measured (needs per-issue comments)

    stars                      INTEGER NOT NULL DEFAULT 0,
    star_velocity_7d           INTEGER NOT NULL DEFAULT 0,
    stargazer_quality          REAL,                    -- null when not measured (sample lacks created_at)
    installs                   INTEGER,                 -- null unless a registry reports it
    forks                      INTEGER NOT NULL DEFAULT 0,
    releases                   INTEGER NOT NULL DEFAULT 0,
    license                    TEXT,
    archived                   INTEGER NOT NULL DEFAULT 0,
    last_commit                TEXT,

    author_track_record        REAL NOT NULL DEFAULT 0.0,
    early_organic_traction     REAL NOT NULL DEFAULT 0.0,

    scope                      TEXT NOT NULL DEFAULT '{}',   -- json {field: "skill"|"repo"}
    flags                      TEXT NOT NULL DEFAULT '[]'    -- json array (anti-gaming.md)
);
