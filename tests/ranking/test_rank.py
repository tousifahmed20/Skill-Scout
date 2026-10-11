"""Stage 08 ranking mechanism (Done-when #3,#4,#5 + the good>hype / pick-first
ordering that #1,#2 rest on). Golden-data #1/#2 need the seeding run (stage 06)."""
import rank as R


def _task(terms, host="claude-code", caps=("do a",)):
    return {"task_text": " ".join(terms), "task_label": "t", "capabilities": list(caps),
            "search_terms": list(terms), "constraints": {"os": None, "free_only": False, "offline": False,
            "language": None}, "host_harness": host}


def _fits(*cids, fit="full"):
    return {c: {"candidate_id": c, "fit": fit, "missing": []} for c in cids}


def test_good_outranks_hype_and_is_pick_one(store_factory):
    specs = [
        {"id": "o/good@s", "text": "pdf report generator convert markdown",
         "health": {"substantive_commits_90d": 20, "independent_contributors": 5, "independent_issue_reports": 8,
                    "forks": 40, "releases": 3, "license": "mit"},
         "eval": {"hype_score": 0.1, "instruction_specificity": 0.9, "example_realism": 0.8}},
        {"id": "o/hype@s", "text": "pdf report generator convert markdown",
         "health": {"substantive_commits_90d": 1, "forks": 2, "flags": ["star_burst"]},
         "eval": {"hype_score": 0.9, "instruction_specificity": 0.2, "example_realism": 0.1,
                  "core_supported": 0, "core_unsupported": 1}},
    ]
    store = store_factory(specs)
    out = R.rank(_task(["pdf", "report", "markdown"]), _fits("o/good@s", "o/hype@s"), store)
    assert out["none_found"] is False
    assert out["picks"][0]["candidate_id"] == "o/good@s"
    scores = {p["candidate_id"]: p["score"] for p in out["picks"]}
    assert scores["o/good@s"] > scores.get("o/hype@s", -1)


def test_nonsense_task_returns_none_found(store_factory):
    store = store_factory([{"id": "o/good@s", "text": "pdf report generator", "eval": {}}])
    out = R.rank(_task(["qwxzjk", "zzzxyq"]), _fits("o/good@s"), store)
    assert out["none_found"] is True and out["picks"] == []


def test_incompatible_host_is_set_aside_not_picked(store_factory):
    specs = [{"id": "o/forky@s", "text": "spawn subagent hooks workflow",
              "eval": {"depends": ["hooks"]},
              "compat": {"harness": {"codex": {"level": "partial", "reasons": []}}, "requirements": {}}}]
    store = store_factory(specs)
    out = R.rank(_task(["spawn", "subagent", "hooks"], host="codex"), _fits("o/forky@s"), store)
    # codex lacks hooks -> effective incompatible -> set aside, never a pick
    assert all(p["candidate_id"] != "o/forky@s" for p in out["picks"])
    assert any(s["candidate_id"] == "o/forky@s" for s in out["set_aside"])


def test_floor_drops_low_credibility(store_factory):
    specs = [{"id": "o/weak@s", "text": "pdf report",
              "eval": {"core_supported": 0, "core_unsupported": 2}}]   # cred low + unsupported core > 1
    store = store_factory(specs)
    out = R.rank(_task(["pdf", "report"]), _fits("o/weak@s"), store)
    assert out["none_found"] is True


def test_hidden_gem_fills_slot_three(store_factory):
    from datetime import date, timedelta
    recent = (date.today() - timedelta(days=7)).isoformat()
    # 3 strong established skills fill the normal top 3; the gem scores low on
    # normal signals (weak health) but high on gem signals, so it takes slot 3.
    strong = {"health": {"substantive_commits_90d": 30, "independent_contributors": 8, "forks": 60,
                         "releases": 4, "license": "mit", "independent_issue_reports": 10},
              "eval": {"hype_score": 0.1, "instruction_specificity": 0.8, "example_realism": 0.8}}
    specs = [
        {"id": "o/a@s", "text": "pdf report convert", **strong},
        {"id": "o/b@s", "text": "pdf report convert", **strong},
        {"id": "o/c@s", "text": "pdf report convert", **strong},
        {"id": "o/gem@s", "text": "pdf report convert", "first_seen": recent,
         "files": {"scripts": ["run.py"], "references": ["g.md"]},
         "health": {"author_track_record": 0.9, "early_organic_traction": 0.8},
         "eval": {"hype_score": 0.05, "instruction_specificity": 0.95, "example_realism": 0.9}},
    ]
    store = store_factory(specs)
    out = R.rank(_task(["pdf", "report", "convert"]), _fits("o/a@s", "o/b@s", "o/c@s", "o/gem@s"), store)
    assert len(out["picks"]) == 3
    gem = out["picks"][2]
    assert gem["candidate_id"] == "o/gem@s" and gem["badge"] == "hidden-gem"


def test_popular_but_unproven_flag(store_factory):
    specs = [
        {"id": "o/pop@s", "text": "pdf report convert",
         "health": {"forks": 500}, "eval": {"core_supported": 2, "core_unsupported": 1, "hype_score": 0.8}},
        {"id": "o/soln@s", "text": "pdf report convert",
         "health": {"forks": 1}, "eval": {"core_supported": 3, "hype_score": 0.1}},
    ]
    store = store_factory(specs)
    out = R.rank(_task(["pdf", "report", "convert"]), _fits("o/pop@s", "o/soln@s"), store)
    pop = next(p for p in out["picks"] if p["candidate_id"] == "o/pop@s")
    assert "popular_but_unproven" in pop["flags"]


def test_task_template_is_valid_json():
    import json
    assert set(R.TASK_TEMPLATE) >= {"task_text", "capabilities", "search_terms", "host_harness"}
    json.dumps(R.TASK_TEMPLATE)
