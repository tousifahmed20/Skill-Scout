from src.collector.dedupe import collapse, content_hash


def test_content_hash_order_independent():
    a = {"SKILL.md": b"hello\n", "scripts/x.py": b"print(1)\n"}
    b = {"scripts/x.py": b"print(1)\n", "SKILL.md": b"hello\n"}  # different dict order
    assert content_hash(a) == content_hash(b)


def test_content_hash_normalizes_line_endings():
    lf = {"SKILL.md": b"a\nb\nc\n"}
    crlf = {"SKILL.md": b"a\r\nb\r\nc\r\n"}
    assert content_hash(lf) == content_hash(crlf)


def test_content_hash_changes_on_content_and_path():
    base = {"SKILL.md": b"x\n"}
    assert content_hash(base) != content_hash({"SKILL.md": b"y\n"})
    assert content_hash(base) != content_hash({"SKILL.MD": b"x\n"})  # path is hashed


def test_fork_collapses_into_source():
    h = "deadbeef"
    source = {"candidate_id": "orig/repo@skills/a", "content_hash": h,
              "first_seen": "2024-01-01", "duplicates": []}
    fork = {"candidate_id": "forker/repo@skills/a", "content_hash": h,
            "first_seen": "2025-06-01", "duplicates": []}
    canonicals, collapsed = collapse([fork, source])  # pass fork first on purpose
    assert collapsed == 1
    assert len(canonicals) == 1
    canon = canonicals[0]
    assert canon["candidate_id"] == "orig/repo@skills/a"          # earliest first_seen
    assert canon["duplicates"] == ["forker/repo@skills/a"]


def test_distinct_hashes_not_collapsed():
    rows = [
        {"candidate_id": "a/r@x", "content_hash": "h1", "first_seen": "2024-01-01", "duplicates": []},
        {"candidate_id": "b/r@y", "content_hash": "h2", "first_seen": "2024-01-01", "duplicates": []},
    ]
    canonicals, collapsed = collapse(rows)
    assert collapsed == 0 and len(canonicals) == 2
