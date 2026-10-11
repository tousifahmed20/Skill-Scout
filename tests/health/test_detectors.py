"""Done-when #1: each detector flags its seeded fixture and not its clean control.
Plus measure sanity and the stargazer id-proxy branch."""
import json
from pathlib import Path

from src.health.compute import compute, _established, _now

FIX = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "gaming"

DETECTORS = ["star_burst", "commit_padding", "sock_puppets", "self_filed_issues"]
FILE = {"star_burst": "star-burst", "commit_padding": "commit-padding",
        "sock_puppets": "sock-puppets", "self_filed_issues": "self-filed-issues"}


def _raw(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def test_each_detector_flags_positive_and_not_control():
    for flag in DETECTORS:
        pos = compute(_raw(FILE[flag]))
        ctrl = compute(_raw(FILE[flag] + "-clean"))
        assert flag in pos["flags"], f"{flag}: positive fixture not flagged ({pos['flags']})"
        assert flag not in ctrl["flags"], f"{flag}: clean control flagged ({ctrl['flags']})"
        assert ctrl["flags"] == [], f"{flag}: control tripped other detectors {ctrl['flags']}"


def test_positive_fixtures_are_single_flag():
    for flag in DETECTORS:
        assert compute(_raw(FILE[flag]))["flags"] == [flag]


def test_self_filed_vs_independent_counts():
    assert compute(_raw("self-filed-issues"))["independent_issue_reports"] == 0
    ctrl = compute(_raw("self-filed-issues-clean"))
    assert ctrl["independent_issue_reports"] == 2
    assert ctrl["linked_fix_closures"] == 1
    assert ctrl["closed_without_fix"] == 1
    assert ctrl["maintainer_first_response_h"] == 18.0  # median(6, 30)


def test_commit_padding_control_has_substantive_commits():
    ctrl = compute(_raw("commit-padding-clean"))
    assert ctrl["substantive_commits_90d"] == 12
    assert ctrl["median_diff_lines"] == 42
    pad = compute(_raw("commit-padding"))
    assert pad["substantive_commits_90d"] == 0  # 1-line commits are below the floor


def test_star_velocity_and_quality():
    burst = compute(_raw("star-burst"))
    assert burst["star_velocity_7d"] == 25
    assert burst["stargazer_quality"] == 0.0   # all known-unestablished (10d-old accounts)
    clean = compute(_raw("star-burst-clean"))
    assert clean["stargazer_quality"] == 1.0   # all established


def test_established_is_tristate_and_quality_none_when_unknown():
    now = _now({"fetched_at": "2026-10-11T00:00:00+00:00"})
    assert _established({"created_at": "2018-01-01", "public_repos": 5}, now) is True
    assert _established({"created_at": "2026-10-01", "public_repos": 5}, now) is False  # too young
    assert _established({"id": 1}, now) is None                                         # no created_at -> unknown
    # A sample with no created_at (e.g. live stargazers) -> quality not measured.
    raw = {"fetched_at": "2026-10-11T00:00:00+00:00", "repo_meta": {"stars": 50},
           "stargazers": [{"login": f"u{i}", "id": i, "starred_at": "2026-10-10T00:00:00+00:00"} for i in range(50)]}
    rec = compute(raw)
    assert rec["stargazer_quality"] is None
    assert rec["star_velocity_7d"] == 50          # velocity needs only starred_at
    assert "star_burst" not in rec["flags"]       # unknown establishment -> no false fire
