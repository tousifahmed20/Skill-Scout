"""SQLite connection + migration runner (v1 DB; single home: CLAUDE.md).

`migrate()` applies every `src/*/schema.sql`. Each stage owns its own
`schema.sql` and must write it idempotently (CREATE TABLE IF NOT EXISTS), so
running the migration repeatedly is safe.

Run:  python -m src.db.core.db        # create/migrate the pipeline DB
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
# Pipeline DB (gitignored) — single home for this path is CLAUDE.md.
DEFAULT_DB = REPO_ROOT / "data" / "index" / "skill-scout.sqlite"


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def schema_files(src_root: Path | str = REPO_ROOT / "src") -> list[Path]:
    return sorted(Path(src_root).glob("*/schema.sql"))


def migrate(conn: sqlite3.Connection, src_root: Path | str = REPO_ROOT / "src") -> list[str]:
    applied = []
    for sql in schema_files(src_root):
        conn.executescript(sql.read_text(encoding="utf-8"))
        applied.append(sql.parent.name)
    conn.commit()
    return applied


if __name__ == "__main__":
    c = connect()
    print("migrated:", migrate(c) or "(no schema.sql found)")
    print("db:", DEFAULT_DB)
    c.close()
