"""Locks for rules not covered by the fixture set: R8 (cross-harness tool),
R9 (MCP requirement), declared-compatibility conflict, and requirements."""
from src.compatibility.checker import check_skill, load_profiles

PROFILES = load_profiles()


def _skill(body, extra_fm=""):
    return f"---\nname: s\ndescription: a test skill for rule checks here now\n{extra_fm}---\n# S\n{body}\n"


def test_r8_task_tool_partial_on_non_claude_code():
    rec = check_skill(_skill("First, use the Task tool to spawn a subagent.\nThen continue.\n"),
                      ["SKILL.md"], "s", PROFILES)
    assert rec["harness"]["claude-code"]["level"] == "compatible"
    assert rec["harness"]["codex"]["level"] == "partial"
    assert any("R8" in r for r in rec["harness"]["codex"]["reasons"])


def test_r9_mcp_server_becomes_requirement_not_incompatible():
    # Every profiled harness supports MCP, so an MCP reference is a requirement.
    rec = check_skill(_skill("Call mcp__playwright__navigate to open the page.\n"),
                      ["SKILL.md"], "s", PROFILES)
    assert "playwright" in rec["requirements"]["mcp_servers"]
    assert rec["harness"]["codex"]["level"] == "compatible"
    assert rec["requirements"]["network"] is True


def test_declared_conflict_when_named_harness_incompatible():
    # compatibility claims codex, but ${CLAUDE_PLUGIN_ROOT} makes codex incompatible (R6).
    rec = check_skill(
        _skill("Run python ${CLAUDE_PLUGIN_ROOT}/scripts/go.py\n", extra_fm="compatibility: [codex]\n"),
        ["SKILL.md"], "s", PROFILES)
    assert rec["harness"]["codex"]["level"] == "incompatible"
    assert rec["declared_compatibility"] == ["codex"]
    assert rec["declared_conflict"] is True


def test_requirements_runtime_os_tools_services():
    body = "Run the helper and call the API.\nUse OPENAI_API_KEY over https.\n"
    rec = check_skill(_skill(body), ["SKILL.md", "scripts/run.py", "scripts/win.ps1"], "s",
                      PROFILES, {"scripts/run.py": "import sys\n", "scripts/win.ps1": "echo hi\n"})
    req = rec["requirements"]
    assert "python" in req["runtimes"]
    assert "windows" in req["os"]
    assert any(s["key_env"] == "OPENAI_API_KEY" and s["paid"] for s in req["services"])


def test_no_conflict_without_declared_field():
    rec = check_skill(_skill("Plain steps here.\nMore steps.\n"), ["SKILL.md"], "s", PROFILES)
    assert rec["declared_compatibility"] is None
    assert rec["declared_conflict"] is False
