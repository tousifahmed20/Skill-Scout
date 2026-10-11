"""Done-when: an evaluator-targeted fixture sets injection_detected; a normal
skill whose steps instruct the agent does not. Tests the deterministic scanner
(defense in depth alongside the model's own rubric judgment)."""
from pathlib import Path

import fetch_evidence as FE

FIX = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "injection"


def _text(name):
    return (FIX / f"{name}.md").read_text(encoding="utf-8")


def test_evaluator_targeting_flagged():
    for name in ("evaluator-target", "override", "exfiltration", "hidden-zerowidth"):
        flagged, detail = FE.scan_injection(_text(name))
        assert flagged, f"{name} not flagged"
        assert detail


def test_normal_task_steps_not_flagged():
    flagged, _ = FE.scan_injection(_text("normal-steps"))
    assert not flagged


def test_plain_instructions_are_not_injection():
    # "run the tests", "ask the user" are normal steps, never injection.
    for s in ["Run the tests and report failures.", "Ask the user for the input file.",
              "Score each row against the rubric and total the points."]:
        assert FE.scan_injection(s)[0] is False, s
