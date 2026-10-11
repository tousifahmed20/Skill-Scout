-- Stage 05 (clustering) owns these tables. SQLite. Idempotent.
-- Field meanings: stages/05_clustering/CONTEXT.md
-- The search tables (search_doc, search_fts) are created by search.build_index,
-- not here: search_fts is an FTS5 virtual table that may be unavailable at
-- migrate time, so build_index creates what the environment supports.

CREATE TABLE IF NOT EXISTS embedding (
    candidate_id TEXT PRIMARY KEY,
    content_hash TEXT,                 -- stale when candidate.content_hash changes
    model        TEXT NOT NULL,        -- embed.MODEL used
    dim          INTEGER NOT NULL,
    vector       TEXT NOT NULL,        -- json array of floats (normalized)
    text         TEXT NOT NULL         -- the text that was embedded
);

CREATE TABLE IF NOT EXISTS cluster (
    cluster_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    grp               TEXT,            -- optional grouping key (category), null = global
    label             TEXT NOT NULL,   -- 3-6 word name
    seed_candidate_id TEXT NOT NULL,
    size              INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cluster_member (
    cluster_id   INTEGER NOT NULL,
    candidate_id TEXT NOT NULL,
    similarity   REAL,                 -- cosine to the seed
    PRIMARY KEY (cluster_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS idx_cluster_member_cand ON cluster_member(candidate_id);
