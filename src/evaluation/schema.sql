-- Stage 06 (evaluation) owns this table. SQLite. Idempotent.
-- Schema/field meanings: skills/skill-scout/references/evaluation-rubric.md
-- Evaluations are cached by content_hash (task-independent). The build imports
-- committed seed files; it makes no LLM calls. status='stale' when the skill's
-- content_hash no longer matches the current candidate.

CREATE TABLE IF NOT EXISTS evaluation (
    candidate_id            TEXT NOT NULL,
    content_hash            TEXT NOT NULL,
    commit_sha              TEXT,
    evaluator_model         TEXT,
    actually_does           TEXT,
    capabilities            TEXT NOT NULL DEFAULT '[]',   -- json
    claims                  TEXT NOT NULL DEFAULT '[]',   -- json
    features                TEXT NOT NULL DEFAULT '[]',   -- json
    limitations             TEXT NOT NULL DEFAULT '[]',   -- json
    issue_resolution        TEXT NOT NULL DEFAULT '{}',   -- json
    instruction_specificity REAL,
    example_realism         REAL,
    hype_score              REAL,
    core_depends_on         TEXT NOT NULL DEFAULT '[]',   -- json
    injection_detected      INTEGER NOT NULL DEFAULT 0,
    injection_detail        TEXT,
    evaluator_confidence    REAL,
    status                  TEXT NOT NULL CHECK (status IN ('active','stale')),
    source_file             TEXT,
    imported_at             TEXT,
    PRIMARY KEY (candidate_id, content_hash)
);
CREATE INDEX IF NOT EXISTS idx_evaluation_cand ON evaluation(candidate_id);
