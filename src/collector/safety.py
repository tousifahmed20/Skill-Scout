"""Safety gate: run an EXISTING agent-skill security scanner over a checked-out
skill folder. CLAUDE.md is explicit: reuse a scanner, do not build one. So this
module is only the integration seam — it shells out to a configured scanner and
normalizes its result; it contains no detection logic of its own.

Configure via env `AF_SAFETY_SCANNER`: a command template where `{dir}` is the
skill folder. The scanner must exit 0 = pass, non-zero = findings; stdout is
captured as the finding detail. Example:
    AF_SAFETY_SCANNER="some-skill-scanner --json {dir}"

If unset, scanning is 'skipped' (candidate stays active, flagged) rather than
silently 'pass' — so a missing scanner is visible, not mistaken for safe.

Open decision (PROGRESS.md): pick the concrete scanner + verify its license.
"""
from __future__ import annotations
import os
import shlex
import subprocess
from pathlib import Path


def scan(local_dir: Path | str, scanner_cmd: str | None = None) -> dict:
    cmd = scanner_cmd if scanner_cmd is not None else os.environ.get("AF_SAFETY_SCANNER")
    if not cmd:
        return {"scanner": None, "status": "skipped",
                "findings": ["AF_SAFETY_SCANNER not configured"]}
    argv = [a.format(dir=str(local_dir)) for a in shlex.split(cmd)]
    name = Path(argv[0]).name
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"scanner": name, "status": "warn",
                "findings": [f"scanner did not run: {e.__class__.__name__}"]}
    if p.returncode == 0:
        return {"scanner": name, "status": "pass", "findings": []}
    detail = (p.stdout or p.stderr or "").strip()
    return {"scanner": name, "status": "fail",
            "findings": [line for line in detail.splitlines() if line.strip()][:50]}


# status -> candidate.status. 'skipped'/'warn' keep the candidate; 'fail' excludes.
def candidate_status(safety: dict) -> str:
    return "excluded_unsafe" if safety.get("status") == "fail" else "active"
