#!/usr/bin/env python3
"""Opt-in with/without-skill verification helper (stage 07). Standard library
only. Does the bookkeeping around the run described in
references/verification-protocol.md; the actual agent runs happen in the user's
harness, driven by steps/05-verify.md.

    python verify.py --estimate <candidate_id> --harness <id>   # token cost, before any run
    python verify.py --setup <candidate_id>                      # make temp folder, download skill files
    python verify.py --finish verify-<candidate>.json           # validate record, delete temp folder

Safety: downloads use the user's own GitHub access (github_auth); files are
written only inside a temporary folder, which --finish deletes. A skill that
contains scripts is reported so the runtime asks a second time before running.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import github_auth

RAW = "https://raw.githubusercontent.com"
PROFILES = Path(__file__).resolve().parent.parent / "references" / "harness-profiles.json"
SESSIONS = Path(github_auth.config_path()).parent / "verify_sessions.json"
SCRIPT_EXT = {".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".ps1", ".rb", ".pl"}

# Token model (verification-protocol.md: 3 tasks, baseline + treatment + blind judge).
TASKS = 3
TASK_PROMPT_TOKENS = 200
OUTPUT_TOKENS = 700
CRITERIA_TOKENS = 120
JUDGE_OUTPUT_TOKENS = 150


def _default_db() -> Path:
    import os
    return Path(os.environ.get("SKILL_SCOUT_INDEX") or (Path.home() / ".skill-scout" / "index.sqlite"))


def resolve(candidate_id: str, db: Path) -> dict:
    if not Path(db).exists():
        raise FileNotFoundError(f"index not found at {db}; run the skill's setup to download it first")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT candidate_id, repo, skill_path, commit_sha FROM candidate WHERE candidate_id=?",
                       (candidate_id,)).fetchone()
    conn.close()
    if not row:
        raise KeyError(f"{candidate_id} not in index {db}")
    return dict(row)


def _raw(repo: str, sha: str, path: str) -> bytes | None:
    url = f"{RAW}/{repo}/{sha}/{urllib.parse.quote(path)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "skill-scout"}), timeout=30) as r:
            return r.read()
    except urllib.error.URLError:
        return None


def _runner(harness_id: str) -> str | None:
    prof = json.loads(PROFILES.read_text(encoding="utf-8"))
    h = next((x for x in prof["harnesses"] if x["id"] == harness_id), None)
    if not h:
        raise KeyError(f"unknown harness '{harness_id}'")
    if h.get("verification_runner") and "verification_runner" not in h.get("unverified", []):
        return h["verification_runner"]
    return None                                    # not verified -> do not offer the test here


def _folder_files(loc: dict, token) -> list[str]:
    repo, sp, sha = loc["repo"], loc["skill_path"], loc["commit_sha"]
    data, _ = github_auth.api_get(f"/repos/{repo}/git/trees/{sha}?recursive=1", token)
    prefix = "" if sp in ("", ".") else sp.rstrip("/") + "/"
    return [t["path"][len(prefix):] for t in data.get("tree", [])
            if t.get("type") == "blob" and (not prefix or t["path"].startswith(prefix))]


def estimate_tokens(skill_md: str) -> int:
    skill = len(skill_md) // 4
    per_task = (TASK_PROMPT_TOKENS + OUTPUT_TOKENS                       # baseline
                + TASK_PROMPT_TOKENS + skill + OUTPUT_TOKENS            # treatment
                + 2 * OUTPUT_TOKENS + CRITERIA_TOKENS + JUDGE_OUTPUT_TOKENS)  # blind judge
    return TASKS * per_task


# ---- sessions (so --finish can find the temp folder from the record) ---------
def _load_sessions() -> dict:
    try:
        return json.loads(SESSIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_sessions(s: dict) -> None:
    SESSIONS.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS.write_text(json.dumps(s), encoding="utf-8")


# ---- commands ----------------------------------------------------------------
def cmd_estimate(candidate_id: str, harness: str, db: Path) -> int:
    runner = _runner(harness)
    if not runner:
        print(f"Verification is not offered for '{harness}': no verified non-interactive runner.", file=sys.stderr)
        return 3
    loc = resolve(candidate_id, db)
    md = _raw(loc["repo"], loc["commit_sha"], ("SKILL.md" if loc["skill_path"] in ("", ".")
                                               else loc["skill_path"].rstrip("/") + "/SKILL.md"))
    skill_md = md.decode("utf-8", "replace") if md else ""
    est = estimate_tokens(skill_md)
    print(json.dumps({"candidate_id": candidate_id, "harness": harness, "runner": runner,
                      "estimated_tokens": est, "tasks": TASKS,
                      "note": "approx; covers baseline + treatment + blind judge for 3 tasks"}))
    return 0


def cmd_setup(candidate_id: str, db: Path) -> int:
    loc = resolve(candidate_id, db)
    token, _ = github_auth.get_token()
    tmp = Path(tempfile.mkdtemp(prefix="skill-scout-verify-"))
    files = _folder_files(loc, token)
    prefix = "" if loc["skill_path"] in ("", ".") else loc["skill_path"].rstrip("/") + "/"
    scripts = []
    for rel in files:
        data = _raw(loc["repo"], loc["commit_sha"], prefix + rel)
        if data is None:
            continue
        dest = tmp / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if rel.startswith("scripts/") or Path(rel).suffix.lower() in SCRIPT_EXT:
            scripts.append(rel)
    sessions = _load_sessions()
    sessions[candidate_id] = str(tmp)
    _save_sessions(sessions)
    out = {"candidate_id": candidate_id, "temp_dir": str(tmp), "files": len(files),
           "scripts_present": bool(scripts), "scripts": sorted(scripts)}
    if scripts:
        out["second_confirmation_required"] = ("This skill contains scripts — ask the user a second time, "
                                               "naming these scripts, before running.")
    print(json.dumps(out))
    return 0


_REQUIRED = ("candidate_id", "harness", "with_score", "without_score", "delta", "verdict")


def validate_record(rec: dict) -> list[str]:
    e = [f"missing {k}" for k in _REQUIRED if k not in rec]
    if e:
        return e
    for k in ("with_score", "without_score", "delta"):
        if not isinstance(rec[k], (int, float)):
            e.append(f"{k}: must be a number")
    if e:
        return e
    if abs((rec["with_score"] - rec["without_score"]) - rec["delta"]) > 1e-6:
        e.append("delta must equal with_score - without_score")
    d = rec["delta"]
    want = "gain" if d > 0.05 else ("worse" if d < -0.05 else "no_measurable_gain")
    if rec["verdict"] != want:
        e.append(f"verdict '{rec['verdict']}' does not match delta {d:+.3f} (expected '{want}')")
    if rec.get("status", "single") not in ("single", "confirmed", "disputed"):
        e.append("status must be single|confirmed|disputed")
    return e


def cmd_finish(record_path: str) -> int:
    try:
        rec = json.loads(Path(record_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as ex:
        print(f"ERROR: cannot read record: {ex}", file=sys.stderr)
        return 1
    errors = validate_record(rec)
    if errors:
        for e in errors:
            print("ERROR:", e, file=sys.stderr)
        return 1
    sessions = _load_sessions()
    path = sessions.pop(rec["candidate_id"], None)
    deleted = False
    if path:
        p = Path(path)
        # delete only a folder we created under the system temp dir (never a user path)
        if p.is_dir() and str(p).startswith(tempfile.gettempdir()) and p.name.startswith("skill-scout-verify-"):
            shutil.rmtree(p, ignore_errors=True)
            deleted = True
        _save_sessions(sessions)
    print(json.dumps({"valid": True, "verdict": rec["verdict"], "temp_dir_deleted": deleted}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="verify.py")
    ap.add_argument("--estimate", metavar="CANDIDATE_ID")
    ap.add_argument("--harness")
    ap.add_argument("--setup", metavar="CANDIDATE_ID")
    ap.add_argument("--finish", metavar="RECORD_JSON")
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else _default_db()
    if a.estimate:
        if not a.harness:
            print("--estimate requires --harness", file=sys.stderr)
            return 2
        return cmd_estimate(a.estimate, a.harness, db)
    if a.setup:
        return cmd_setup(a.setup, db)
    if a.finish:
        return cmd_finish(a.finish)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
