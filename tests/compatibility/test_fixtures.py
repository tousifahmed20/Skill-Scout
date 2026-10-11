"""Done-when #1: every fixture produces its expected level for every
default-display harness."""
from pathlib import Path

import pytest

from src.compatibility.checker import check_skill, load_profiles

FIXTURES = Path("data/fixtures/compat")
PROFILES = load_profiles()
DEFAULT = PROFILES["default_display"]
OTHERS = [h for h in DEFAULT if h != "claude-code"]

# fixture -> {harness_id: expected_level}. "cc" = claude-code, "others" = the
# rest of the default-display set.
EXPECT = {
    "portable":      {"all": "compatible"},
    "cc-keys":       {"cc": "compatible", "others": "partial"},
    "fork":          {"cc": "compatible", "others": "partial"},
    "hooks":         {"cc": "compatible", "others": "partial"},
    "injection-cmd": {"cc": "compatible", "others": "partial"},
    "arguments":     {"cc": "compatible", "others": "partial"},
    "plugin-root":   {"cc": "compatible", "others": "incompatible"},
    "allowed-tools": {"all": "compatible"},
    "outside-ref":   {"all": "partial"},
    "name-mismatch": {"all": "partial"},
    "bash-script":   {"all": "compatible"},
    "paid-api":      {"all": "compatible"},
}


def _load(fid: str):
    folder = FIXTURES / fid
    files, texts = [], {}
    for p in sorted(folder.rglob("*")):
        if p.is_file():
            rel = p.relative_to(folder).as_posix()
            files.append(rel)
            texts[rel] = p.read_text(encoding="utf-8")
    return check_skill(texts["SKILL.md"], files, fid, PROFILES, texts)


def _expected(spec: dict, harness: str) -> str:
    if "all" in spec:
        return spec["all"]
    return spec["cc"] if harness == "claude-code" else spec["others"]


@pytest.mark.parametrize("fid", list(EXPECT))
def test_fixture_levels(fid):
    rec = _load(fid)
    for h in DEFAULT:
        got = rec["harness"][h]["level"]
        want = _expected(EXPECT[fid], h)
        assert got == want, f"{fid}/{h}: got {got}, want {want} ({rec['harness'][h]['reasons']})"


def test_bash_script_requires_posix_os():
    rec = _load("bash-script")
    assert rec["requirements"]["os"] == ["linux", "macos"]
    assert "bash" in rec["requirements"]["runtimes"]


def test_paid_api_records_paid_service():
    rec = _load("paid-api")
    svcs = rec["requirements"]["services"]
    assert any(s["key_env"] == "OPENAI_API_KEY" and s["paid"] for s in svcs)
    assert rec["requirements"]["network"] is True


def test_portable_has_no_reasons_anywhere():
    rec = _load("portable")
    for h in DEFAULT:
        assert rec["harness"][h]["reasons"] == []
