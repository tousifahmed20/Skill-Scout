#!/usr/bin/env python3
"""Print the host coding harness id, or `unknown` (stage 09). Standard library.

Detection uses each harness's `detect_env` in references/harness-profiles.json
(the single source for host facts). Only harnesses with a documented env marker
can be detected non-interactively — the rest return `unknown`, and the skill
asks the user once.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

PROFILES = Path(__file__).resolve().parent.parent / "references" / "harness-profiles.json"


def detect(env=None) -> str:
    env = os.environ if env is None else env
    prof = json.loads(PROFILES.read_text(encoding="utf-8"))
    for h in prof["harnesses"]:
        de = h.get("detect_env")
        if de and all(env.get(k) == v for k, v in de.items()):
            return h["id"]
    return "unknown"


if __name__ == "__main__":
    print(detect())
