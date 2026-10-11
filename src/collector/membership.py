"""Membership gate: is this folder a real agent skill?

Rules: stages/02_collector/references/membership.md. This gate judges only
"is it a real skill", never quality/popularity (those are later stages).

`evaluate()` takes the candidate folder's file list and its SKILL.md text (or
None if there is no exact-case SKILL.md) and returns Accept or Reject.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

import yaml

# Spec frontmatter keys (membership.md). Anything else is a warning, not a reject.
SPEC_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")  # spec: lowercase, digits, hyphens
MAX_NAME_LEN = 64
MAX_DESC_LEN = 1024
MAX_SKILL_LINES = 500
# At least this many real (non-template) body lines, or it's a placeholder.
# Tune against the reject sample (membership.md).
MIN_BODY_LINES = 5
_PLACEHOLDER = re.compile(
    r"\btodo\b|describe your skill here|your skill here|lorem ipsum|<[^>]*placeholder[^>]*>",
    re.IGNORECASE,
)


@dataclass
class Accept:
    name: str
    description: str
    frontmatter_keys: list[str]
    spec_warnings: list[str] = field(default_factory=list)
    body_lines: int = 0
    accepted: bool = True


@dataclass
class Reject:
    reason: str   # one of membership.md's reason enum
    detail: str = ""
    accepted: bool = False


def skill_md_status(folder_files: list[str]) -> str:
    """'ok' if an exact-case SKILL.md exists at the folder top; 'wrong_filename'
    if only a cased variant exists; 'absent' otherwise. folder_files are paths
    relative to the candidate folder."""
    tops = [f for f in folder_files if "/" not in f.strip("/")]
    if "SKILL.md" in tops:
        return "ok"
    if any(f.lower() == "skill.md" for f in tops):
        return "wrong_filename"
    return "absent"


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return (frontmatter_yaml, body). frontmatter is None if no leading
    `---` block is present."""
    m = re.match(r"^﻿?---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)$", text, re.S)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def _real_body_lines(body: str) -> int:
    n = 0
    for line in body.splitlines():
        s = line.strip()
        if not s or _PLACEHOLDER.search(s):
            continue
        n += 1
    return n


def evaluate(folder_files: list[str], skill_md_text: str | None, folder_name: str):
    """Apply the membership gate to one candidate folder."""
    if skill_md_text is None:
        status = skill_md_status(folder_files)
        if status == "wrong_filename":
            return Reject("wrong_filename", "found skill.md with non-canonical casing")
        return Reject("no_skill_md", "no SKILL.md in folder")

    fm, body = split_frontmatter(skill_md_text)
    if fm is None:
        return Reject("bad_frontmatter", "no YAML frontmatter block")
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError as e:
        return Reject("bad_frontmatter", f"unparseable YAML: {e.__class__.__name__}")
    if not isinstance(data, dict):
        return Reject("bad_frontmatter", "frontmatter is not a mapping")

    name = data.get("name")
    desc = data.get("description")
    if not (isinstance(name, str) and name.strip()):
        return Reject("bad_frontmatter", "missing or empty name")
    if not (isinstance(desc, str) and desc.strip()):
        return Reject("bad_frontmatter", "missing or empty description")

    if _real_body_lines(body) < MIN_BODY_LINES:
        return Reject("placeholder", f"fewer than {MIN_BODY_LINES} real body lines")

    keys = list(data.keys())
    warnings: list[str] = []
    if name != folder_name:
        warnings.append("name_differs_from_folder")
    if not NAME_RE.match(name) or len(name) > MAX_NAME_LEN:
        warnings.append("name_breaks_spec_chars")
    if len(desc) > MAX_DESC_LEN:
        warnings.append("description_too_long")
    if skill_md_text.count("\n") + 1 > MAX_SKILL_LINES:
        warnings.append("skill_md_too_long")
    extra = [k for k in keys if k not in SPEC_KEYS]
    if extra:
        warnings.append("nonspec_frontmatter_keys:" + ",".join(sorted(extra)))
    if re.search(r"(^|[\s(\[\"'`])\.\./", skill_md_text):
        warnings.append("references_outside_folder")

    return Accept(name=name.strip(), description=desc.strip(),
                  frontmatter_keys=keys, spec_warnings=warnings,
                  body_lines=_real_body_lines(body))
