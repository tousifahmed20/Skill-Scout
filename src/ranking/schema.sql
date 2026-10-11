-- Stage 08 (ranking) owns these slot tables. SQLite. Idempotent.
-- Field meanings: stages/08_ranking/references/scoring.md (#signal-slots).
-- Empty in v1: external_reports is filled by stage 11, outcome_reports through
-- the Store (stages 09/10). Ranking reads them only when rows exist.

CREATE TABLE IF NOT EXISTS external_reports (
    candidate_id  TEXT NOT NULL,
    url           TEXT NOT NULL,
    source        TEXT,
    posted_at     TEXT,
    firsthand     INTEGER NOT NULL DEFAULT 0,   -- author says they used it
    sentiment     TEXT CHECK (sentiment IN ('positive','negative','mixed','neutral')),
    summary       TEXT,                          -- <= 200 chars
    launch_window INTEGER NOT NULL DEFAULT 0,    -- inside a coordinated-launch cluster
    PRIMARY KEY (candidate_id, url)
);
CREATE INDEX IF NOT EXISTS idx_external_reports_cand ON external_reports(candidate_id);

CREATE TABLE IF NOT EXISTS outcome_reports (
    candidate_id   TEXT NOT NULL,
    worked         TEXT NOT NULL CHECK (worked IN ('yes','partial','no')),
    harness        TEXT,
    note           TEXT,                          -- <= 200 chars
    contributor_id TEXT,
    created_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_outcome_reports_cand ON outcome_reports(candidate_id);
