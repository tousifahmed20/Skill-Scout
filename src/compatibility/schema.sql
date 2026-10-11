-- Stage 03 (compatibility) owns this table. SQLite. Idempotent.
-- Record shape: stages/03_compatibility/CONTEXT.md ("Output record").
-- Static analysis only; tested results (stage 07) are stored elsewhere.

CREATE TABLE IF NOT EXISTS compatibility (
    candidate_id           TEXT PRIMARY KEY,
    content_hash           TEXT NOT NULL,          -- record is stale if this changes
    harness                TEXT NOT NULL,          -- json {<harness id>: {level, reasons[]}}
    requirements           TEXT NOT NULL,          -- json {runtimes,os,system_tools,mcp_servers,services,network}
    declared_compatibility TEXT,                   -- json: author's claim, or null
    declared_conflict      INTEGER NOT NULL DEFAULT 0  -- 0/1
);
